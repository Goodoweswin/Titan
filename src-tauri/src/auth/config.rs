use url::Url;

#[derive(Clone)]
pub struct Config {
    pub issuer: Url,
}
impl Config {
    pub fn environment() -> Result<Option<Self>, &'static str> {
        let configured = if cfg!(debug_assertions) {
            std::env::var("TITAN_ACCOUNTS_ISSUER")
                .ok()
                .or_else(|| option_env!("TITAN_ACCOUNTS_ISSUER").map(str::to_owned))
        } else {
            option_env!("TITAN_ACCOUNTS_ISSUER").map(str::to_owned)
        };
        configured
            .map(|s| Self::parse(&s, cfg!(debug_assertions)))
            .transpose()
    }
    pub fn parse(raw: &str, development: bool) -> Result<Self, &'static str> {
        let issuer = Url::parse(raw).map_err(|_| "invalid_configuration")?;
        let local =
            development && issuer.scheme() == "http" && issuer.host_str() == Some("127.0.0.1");
        if !(issuer.scheme() == "https" || local)
            || issuer.host_str().is_none()
            || !issuer.username().is_empty()
            || issuer.password().is_some()
            || issuer.query().is_some()
            || issuer.fragment().is_some()
            || issuer.path() != "/"
            || raw.ends_with('/')
            || raw != issuer.origin().ascii_serialization()
        {
            return Err("invalid_configuration");
        }
        Ok(Self { issuer })
    }
    pub fn issuer_string(&self) -> String {
        self.issuer.origin().ascii_serialization()
    }
    pub fn endpoint(&self, raw: &str) -> Result<Url, &'static str> {
        let url = Url::parse(raw).map_err(|_| "invalid_discovery")?;
        if url.origin() != self.issuer.origin()
            || !url.username().is_empty()
            || url.password().is_some()
            || url.query().is_some()
            || url.fragment().is_some()
        {
            return Err("invalid_discovery");
        }
        Ok(url)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn issuer_is_exact_https_origin_or_explicit_debug_loopback() {
        assert!(Config::parse("https://accounts.example.org", false).is_ok());
        assert!(Config::parse("http://127.0.0.1:8000", true).is_ok());
        for bad in [
            "http://accounts.example.org",
            "http://127.0.0.1:8000/",
            "https://u:p@accounts.example.org",
            "https://accounts.example.org/path",
            "https://accounts.example.org?x=1",
            "https://accounts.example.org#x",
        ] {
            assert!(Config::parse(bad, true).is_err(), "{bad}");
        }
        assert!(Config::parse("http://127.0.0.1:8000", false).is_err());
    }
    #[test]
    fn discovery_endpoints_cannot_escape_issuer_origin() {
        let cfg = Config::parse("https://accounts.example.org", false).unwrap();
        assert!(cfg
            .endpoint("https://accounts.example.org/o/token/")
            .is_ok());
        for bad in [
            "https://evil.example/o/token/",
            "http://accounts.example.org/o/token/",
            "https://accounts.example.org:444/o/token/",
            "https://user@accounts.example.org/o/token/",
            "https://accounts.example.org/o/token/#x",
            "https://accounts.example.org/o/token/?x=1",
        ] {
            assert!(cfg.endpoint(bad).is_err());
        }
    }
}
