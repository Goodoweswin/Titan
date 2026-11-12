use openidconnect::{core::*, *};
use serde::{Deserialize, Serialize};
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct NativeExtras {
    pub refresh_expires_in: u64,
    pub session_id: String,
}
impl ExtraTokenFields for NativeExtras {}
pub type NativeTokenResponse = StandardTokenResponse<
    IdTokenFields<
        EmptyAdditionalClaims,
        NativeExtras,
        CoreGenderClaim,
        CoreJweContentEncryptionAlgorithm,
        CoreJwsSigningAlgorithm,
    >,
    CoreTokenType,
>;
pub fn validate_response(
    response: &NativeTokenResponse,
    previous: Option<(u64, &str)>,
) -> Result<(), &'static str> {
    let extra = response.extra_fields().extra_fields();
    let valid_secret =
        |s: &str| !s.is_empty() && s.len() <= 4096 && s.bytes().all(|b| b.is_ascii_graphic());
    if response.token_type() != &CoreTokenType::Bearer
        || !valid_secret(response.access_token().secret())
        || !response
            .refresh_token()
            .is_some_and(|t| valid_secret(t.secret()))
        || !response
            .expires_in()
            .is_some_and(|v| (1..=600).contains(&v.as_secs()))
        || !(1..=2592000).contains(&extra.refresh_expires_in)
        || extra.session_id.is_empty()
        || extra.session_id.len() > 128
    {
        return Err("invalid_token_response");
    }
    if let Some((expires, id)) = previous {
        if extra.session_id != id
            || now().saturating_add(extra.refresh_expires_in) > expires.saturating_add(2)
        {
            return Err("invalid_token_response");
        }
    }
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    fn response() -> NativeTokenResponse {
        serde_json::from_value(serde_json::json!({"access_token":"access", "refresh_token":"refresh", "token_type":"Bearer", "expires_in":600,"refresh_expires_in":2592000,"session_id":"s1"})).unwrap()
    }
    #[test]
    fn accepts_required_native_token_fields() {
        assert!(validate_response(&response(), None).is_ok());
    }
    #[test]
    fn refuses_missing_refresh_and_absolute_expiry_reset() {
        let mut value = serde_json::to_value(response()).unwrap();
        value["refresh_token"] = serde_json::json!("");
        assert!(validate_response(&serde_json::from_value(value).unwrap(), None).is_err());
        assert!(
            validate_response(&response(), Some((super::super::types::now() + 1000, "s1")))
                .is_err()
        );
        assert!(validate_response(
            &response(),
            Some((super::super::types::now() + 2592000, "other"))
        )
        .is_err());
    }
}

use super::{
    config::Config,
    types::{now, Credentials},
};
use std::time::Duration;
use url::Url;
use zeroize::Zeroizing;
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DiscoveryExtras {
    pub revocation_endpoint: Option<String>,
    #[serde(default)]
    pub code_challenge_methods_supported: Vec<String>,
}
impl AdditionalProviderMetadata for DiscoveryExtras {}
pub type NativeMetadata = ProviderMetadata<
    DiscoveryExtras,
    CoreAuthDisplay,
    CoreClientAuthMethod,
    CoreClaimName,
    CoreClaimType,
    CoreGrantType,
    CoreJweContentEncryptionAlgorithm,
    CoreJweKeyManagementAlgorithm,
    CoreJsonWebKey,
    CoreResponseMode,
    CoreResponseType,
    CoreSubjectIdentifierType,
>;

pub type NativeClient<
    HA = EndpointNotSet,
    HD = EndpointNotSet,
    HI = EndpointNotSet,
    HR = EndpointNotSet,
    HT = EndpointNotSet,
    HU = EndpointNotSet,
> = Client<
    EmptyAdditionalClaims,
    CoreAuthDisplay,
    CoreGenderClaim,
    CoreJweContentEncryptionAlgorithm,
    CoreJsonWebKey,
    CoreAuthPrompt,
    StandardErrorResponse<CoreErrorResponseType>,
    NativeTokenResponse,
    CoreTokenIntrospectionResponse,
    CoreRevocableToken,
    CoreRevocationErrorResponse,
    HA,
    HD,
    HI,
    HR,
    HT,
    HU,
>;
pub struct Login {
    pub metadata: NativeMetadata,
    pub state: CsrfToken,
    pub nonce: Nonce,
    pub verifier: PkceCodeVerifier,
    pub redirect: RedirectUrl,
    pub url: Url,
}
#[derive(Clone)]
pub struct Network {
    pub config: Config,
    pub http: reqwest::Client,
}
#[derive(Debug)]
pub struct TransportError;
impl std::fmt::Display for TransportError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "account transport failed")
    }
}
impl std::error::Error for TransportError {}

impl Network {
    pub fn new(config: Config) -> Result<Self, &'static str> {
        let http = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .connect_timeout(Duration::from_secs(5))
            .timeout(Duration::from_secs(15))
            .no_proxy()
            .build()
            .map_err(|_| "network_unavailable")?;
        Ok(Self { config, http })
    }
    pub async fn limited(
        mut response: reqwest::Response,
        limit: usize,
    ) -> Result<Vec<u8>, &'static str> {
        if response
            .content_length()
            .is_some_and(|len| len > limit as u64)
        {
            return Err("invalid_response");
        }
        let mut bytes = Vec::new();
        while let Some(chunk) = response.chunk().await.map_err(|_| "network_unavailable")? {
            if bytes.len() + chunk.len() > limit {
                return Err("invalid_response");
            }
            bytes.extend_from_slice(&chunk);
        }
        Ok(bytes)
    }
    async fn send(&self, request: HttpRequest) -> Result<HttpResponse, TransportError> {
        self.config
            .endpoint(&request.uri().to_string())
            .map_err(|_| TransportError)?;
        let response = self
            .http
            .execute(request.try_into().map_err(|_| TransportError)?)
            .await
            .map_err(|_| TransportError)?;
        let mut result = http::Response::builder().status(response.status());
        for (name, value) in response.headers() {
            result = result.header(name, value);
        }
        let bytes = Self::limited(response, 65536)
            .await
            .map_err(|_| TransportError)?;
        result.body(bytes).map_err(|_| TransportError)
    }
    pub async fn discover(&self) -> Result<NativeMetadata, &'static str> {
        let discovery = self
            .config
            .issuer
            .join("/.well-known/openid-configuration")
            .map_err(|_| "invalid_discovery")?;
        let response = self
            .http
            .get(discovery)
            .send()
            .await
            .map_err(|_| "network_unavailable")?;
        if response.status() != reqwest::StatusCode::OK {
            return Err("network_unavailable");
        }
        let bytes = Self::limited(response, 262144).await?;
        let mut metadata: NativeMetadata =
            serde_json::from_slice(&bytes).map_err(|_| "invalid_discovery")?;
        if metadata.issuer().as_str() != self.config.issuer_string() {
            return Err("invalid_discovery");
        }
        self.config
            .endpoint(metadata.authorization_endpoint().as_str())?;
        self.config.endpoint(
            metadata
                .token_endpoint()
                .ok_or("invalid_discovery")?
                .as_str(),
        )?;
        self.config.endpoint(metadata.jwks_uri().as_str())?;
        if let Some(url) = metadata.userinfo_endpoint() {
            self.config.endpoint(url.as_str())?;
        }
        if let Some(url) = metadata.additional_metadata().revocation_endpoint.as_ref() {
            self.config.endpoint(url.as_str())?;
        }
        if !metadata
            .additional_metadata()
            .code_challenge_methods_supported
            .iter()
            .any(|m| m == "S256")
        {
            return Err("invalid_discovery");
        }
        if !metadata
            .id_token_signing_alg_values_supported()
            .contains(&CoreJwsSigningAlgorithm::RsaSsaPkcs1V15Sha256)
        {
            return Err("invalid_discovery");
        }
        let response = self
            .http
            .get(metadata.jwks_uri().as_str())
            .send()
            .await
            .map_err(|_| "network_unavailable")?;
        if response.status() != reqwest::StatusCode::OK {
            return Err("invalid_discovery");
        }
        let jwks: CoreJsonWebKeySet =
            serde_json::from_slice(&Self::limited(response, 262144).await?)
                .map_err(|_| "invalid_discovery")?;
        metadata = metadata.set_jwks(jwks);
        Ok(metadata)
    }
    pub async fn prepare(&self, port: u16, switch: bool) -> Result<Login, &'static str> {
        let metadata = self.discover().await?;
        let redirect = RedirectUrl::new(format!("http://127.0.0.1:{port}/oauth/callback"))
            .map_err(|_| "callback_unavailable")?;
        let client = NativeClient::from_provider_metadata(
            metadata.clone(),
            ClientId::new("titan-desktop".into()),
            None,
        )
        .set_redirect_uri(redirect.clone())
        .set_auth_type(AuthType::RequestBody);
        let (challenge, verifier) = PkceCodeChallenge::new_random_sha256();
        let mut request = client
            .authorize_url(
                CoreAuthenticationFlow::AuthorizationCode,
                CsrfToken::new_random,
                Nonce::new_random,
            )
            .add_scope(Scope::new("profile".into()))
            .add_scope(Scope::new("email".into()))
            .set_pkce_challenge(challenge);
        if switch {
            request = request
                .add_prompt(CoreAuthPrompt::Login)
                .set_max_age(Duration::ZERO);
        }
        let (url, state, nonce) = request.url();
        if url.origin() != self.config.issuer.origin() {
            return Err("invalid_discovery");
        }
        Ok(Login {
            metadata,
            state,
            nonce,
            verifier,
            redirect,
            url,
        })
    }
    pub async fn exchange(&self, login: Login, code: String) -> Result<Credentials, &'static str> {
        let client = NativeClient::from_provider_metadata(
            login.metadata,
            ClientId::new("titan-desktop".into()),
            None,
        )
        .set_redirect_uri(login.redirect)
        .set_auth_type(AuthType::RequestBody);
        let response = client
            .exchange_code(AuthorizationCode::new(code))
            .map_err(|_| "invalid_discovery")?
            .set_pkce_verifier(login.verifier)
            .request_async(self)
            .await
            .map_err(|_| "login_failed")?;
        validate_response(&response, None)?;
        let subject = Self::verify_id(&client, &response, &login.nonce, None, true)?;
        Self::credentials(response, subject, login.nonce.secret().clone(), None)
    }
    pub async fn refresh(&self, previous: &Credentials) -> Result<Credentials, &'static str> {
        let metadata = self.discover().await?;
        let client = NativeClient::from_provider_metadata(
            metadata,
            ClientId::new("titan-desktop".into()),
            None,
        )
        .set_auth_type(AuthType::RequestBody);
        let token = RefreshToken::new(previous.refresh.to_string());
        let response = client
            .exchange_refresh_token(&token)
            .map_err(|_| "invalid_discovery")?
            .request_async(self)
            .await
            .map_err(|error| match error {
                RequestTokenError::ServerResponse(error)
                    if error.error().to_string() == "invalid_grant" =>
                {
                    "unauthorized"
                }
                _ => "refresh_ambiguous",
            })?;
        validate_response(
            &response,
            Some((previous.family_expires, &previous.session_id)),
        )?;
        Self::verify_id(
            &client,
            &response,
            &Nonce::new(previous.nonce.clone()),
            Some(&previous.subject),
            false,
        )?;
        Self::credentials(
            response,
            previous.subject.clone(),
            previous.nonce.clone(),
            Some(previous.family_expires),
        )
    }
    fn verify_id<
        HA: EndpointState,
        HD: EndpointState,
        HI: EndpointState,
        HR: EndpointState,
        HT: EndpointState,
        HU: EndpointState,
    >(
        client: &NativeClient<HA, HD, HI, HR, HT, HU>,
        response: &NativeTokenResponse,
        nonce: &Nonce,
        expected: Option<&str>,
        required: bool,
    ) -> Result<String, &'static str> {
        let Some(id) = response.extra_fields().id_token() else {
            return if required {
                Err("invalid_id_token")
            } else {
                Ok(expected.ok_or("invalid_id_token")?.into())
            };
        };
        let verifier = client
            .id_token_verifier()
            .set_allowed_algs(vec![CoreJwsSigningAlgorithm::RsaSsaPkcs1V15Sha256])
            .set_issue_time_verifier_fn(|iat| {
                let timestamp = iat.timestamp();
                if timestamp < 0
                    || timestamp as u64 > now() + 60
                    || now().saturating_sub(timestamp as u64) > 660
                {
                    Err("invalid issue time".into())
                } else {
                    Ok(())
                }
            });
        let claims = id
            .claims(&verifier, |value: Option<&Nonce>| {
                if required || value.is_some() {
                    nonce.verify(value)
                } else {
                    Ok(())
                }
            })
            .map_err(|_| "invalid_id_token")?;
        if claims.expiration() <= claims.issue_time()
            || expected.is_some_and(|subject| claims.subject().as_str() != subject)
        {
            return Err("invalid_id_token");
        }
        if let Some(hash) = claims.access_token_hash() {
            let actual = AccessTokenHash::from_token(
                response.access_token(),
                id.signing_alg().map_err(|_| "invalid_id_token")?,
                id.signing_key(&verifier).map_err(|_| "invalid_id_token")?,
            )
            .map_err(|_| "invalid_id_token")?;
            if hash != &actual {
                return Err("invalid_id_token");
            }
        }
        Ok(claims.subject().as_str().into())
    }
    fn credentials(
        response: NativeTokenResponse,
        subject: String,
        nonce: String,
        previous_expiry: Option<u64>,
    ) -> Result<Credentials, &'static str> {
        let extra = response.extra_fields().extra_fields();
        let family_expires =
            (now() + extra.refresh_expires_in).min(previous_expiry.unwrap_or(u64::MAX));
        Ok(Credentials {
            access: Zeroizing::new(response.access_token().secret().clone()),
            refresh: Zeroizing::new(
                response
                    .refresh_token()
                    .ok_or("invalid_token_response")?
                    .secret()
                    .clone(),
            ),
            access_expires: now()
                + response
                    .expires_in()
                    .ok_or("invalid_token_response")?
                    .as_secs(),
            family_expires,
            subject,
            nonce,
            session_id: extra.session_id.clone(),
        })
    }
    pub async fn api(
        &self,
        method: reqwest::Method,
        path: &str,
        access: &str,
        body: Option<serde_json::Value>,
    ) -> Result<serde_json::Value, &'static str> {
        let mut request = self
            .http
            .request(
                method,
                self.config
                    .issuer
                    .join(path)
                    .map_err(|_| "invalid_request")?,
            )
            .bearer_auth(access);
        if let Some(body) = body {
            request = request.json(&body);
        }
        let response = request.send().await.map_err(|_| "network_unavailable")?;
        let status = response.status();
        let bytes = Self::limited(response, 262144).await?;
        if status == reqwest::StatusCode::NO_CONTENT {
            return Ok(serde_json::Value::Null);
        }
        if status == reqwest::StatusCode::UNAUTHORIZED {
            return Err("unauthorized");
        }
        if !status.is_success() {
            let error = serde_json::from_slice::<serde_json::Value>(&bytes).ok();
            return Err(match error.as_ref().and_then(|v| v["code"].as_str()) {
                Some("recent_auth_required") => "recent_auth_required",
                Some("invalid_profile") => "invalid_profile",
                Some("not_found") => "not_found",
                _ => "service_unavailable",
            });
        }
        serde_json::from_slice(&bytes).map_err(|_| "invalid_response")
    }
    pub async fn profile(
        &self,
        credentials: &Credentials,
    ) -> Result<super::types::Profile, &'static str> {
        let profile: super::types::Profile = serde_json::from_value(
            self.api(
                reqwest::Method::GET,
                "/api/v1/me",
                &credentials.access,
                None,
            )
            .await?,
        )
        .map_err(|_| "invalid_response")?;
        if profile.id != credentials.subject
            || profile.session_id != credentials.session_id
            || !profile.email_verified
        {
            return Err("invalid_id_token");
        }
        Ok(profile)
    }
    pub async fn revoke(&self, credentials: &Credentials) {
        // Uses fixed issuer policy; revocation is best-effort after local credentials are fenced.
        let Ok(metadata) = self.discover().await else {
            return;
        };
        if let Some(endpoint) = metadata.additional_metadata().revocation_endpoint.as_ref() {
            let _ = self
                .http
                .post(endpoint.as_str())
                .form(&[
                    ("client_id", "titan-desktop"),
                    ("token", credentials.refresh.as_str()),
                    ("token_type_hint", "refresh_token"),
                ])
                .send()
                .await;
        }
    }
}

impl<'c> AsyncHttpClient<'c> for Network {
    type Error = TransportError;
    type Future = std::pin::Pin<
        Box<
            dyn std::future::Future<Output = Result<HttpResponse, TransportError>>
                + Send
                + Sync
                + 'c,
        >,
    >;
    fn call(&'c self, request: HttpRequest) -> Self::Future {
        Box::pin(self.send(request))
    }
}
