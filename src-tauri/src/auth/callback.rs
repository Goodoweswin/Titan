use std::time::Duration;
use subtle::ConstantTimeEq;
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::TcpListener,
    sync::watch,
};

pub const MAX_REQUEST: usize = 8192;
#[derive(Debug, PartialEq)]
pub enum Reply {
    Code(String),
    Denied,
}
pub fn parse(bytes: &[u8], port: u16, state: &str, issuer: &str) -> Option<Reply> {
    if bytes.len() > MAX_REQUEST || !bytes.ends_with(b"\r\n\r\n") {
        return None;
    }
    let text = std::str::from_utf8(bytes).ok()?;
    let mut lines = text.split("\r\n");
    let line = lines.next()?;
    let mut parts = line.split(' ');
    if parts.next() != Some("GET") {
        return None;
    }
    let target = parts.next()?;
    if parts.next() != Some("HTTP/1.1") || parts.next().is_some() {
        return None;
    }
    let expected_host = format!("127.0.0.1:{port}");
    let mut host = false;
    for line in lines {
        if line.is_empty() {
            continue;
        }
        let (name, value) = line.split_once(':')?;
        if name.eq_ignore_ascii_case("host") {
            if host || value.trim() != expected_host {
                return None;
            }
            host = true;
        }
        if name.eq_ignore_ascii_case("content-length") && value.trim() != "0" {
            return None;
        }
        if name.eq_ignore_ascii_case("transfer-encoding") {
            return None;
        }
    }
    if !host || target.contains('#') {
        return None;
    }
    let (path, query) = target.split_once('?')?;
    if path != "/oauth/callback" {
        return None;
    }
    let q = query.as_bytes();
    let mut i = 0;
    while i < q.len() {
        if q[i] == b'%' {
            if i + 2 >= q.len() || !q[i + 1].is_ascii_hexdigit() || !q[i + 2].is_ascii_hexdigit() {
                return None;
            }
            i += 2;
        }
        i += 1;
    }
    let mut params = std::collections::HashMap::new();
    for (key, value) in url::form_urlencoded::parse(q) {
        if key.contains(char::is_control)
            || value.contains(char::is_control)
            || key.contains('\u{fffd}')
            || value.contains('\u{fffd}')
        {
            return None;
        }
        if ![
            "code",
            "state",
            "error",
            "error_description",
            "error_uri",
            "iss",
        ]
        .contains(&key.as_ref())
            || params
                .insert(key.into_owned(), value.into_owned())
                .is_some()
        {
            return None;
        }
    }
    if params.get("iss").is_some_and(|value| value != issuer) {
        return None;
    }
    let supplied = params.get("state")?;
    if !bool::from(supplied.as_bytes().ct_eq(state.as_bytes())) {
        return None;
    }
    match (params.get("code"), params.get("error")) {
        (Some(code), None)
            if !code.is_empty()
                && code.len() <= 2048
                && code
                    .bytes()
                    .all(|c| c.is_ascii_alphanumeric() || b"-._~".contains(&c))
                && params.len() == if params.contains_key("iss") { 3 } else { 2 } =>
        {
            Some(Reply::Code(code.clone()))
        }
        (None, Some(error)) if !error.is_empty() => Some(Reply::Denied),
        _ => None,
    }
}

pub async fn receive(
    listener: TcpListener,
    state: &str,
    issuer: &str,
    mut cancel: watch::Receiver<bool>,
    duration: Duration,
) -> Result<String, &'static str> {
    let deadline = tokio::time::sleep(duration);
    tokio::pin!(deadline);
    loop {
        tokio::select! {biased;
          _=cancel.changed()=>return Err("login_cancelled"),
          _=&mut deadline=>return Err("login_timeout"),
          incoming=listener.accept()=>{
            let (mut stream,peer)=incoming.map_err(|_|"callback_unavailable")?;
            if !peer.ip().is_loopback(){continue;}
            let read=async {
                let mut bytes=Vec::with_capacity(1024);
                loop {let mut buf=[0u8;1024];let count=stream.read(&mut buf).await.ok()?;if count==0{return None;}bytes.extend_from_slice(&buf[..count]);if bytes.len()>MAX_REQUEST{return None;}if bytes.windows(4).any(|w|w==b"\r\n\r\n"){break;}}
                parse(&bytes,listener.local_addr().ok()?.port(),state,issuer)
            };
            let result=tokio::select!{biased;_ = cancel.changed()=>return Err("login_cancelled"),_=&mut deadline=>return Err("login_timeout"),r=tokio::time::timeout(Duration::from_secs(2),read)=>r.ok().flatten()};
            let status=if result.is_some(){"200 OK"}else{"400 Bad Request"};
            let body = "Return to Titan to continue login.";
            let length = body.len();
            let response=format!("HTTP/1.1 {status}\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\nReferrer-Policy: no-referrer\r\nContent-Security-Policy: default-src 'none'\r\nConnection: close\r\nContent-Length: {length}\r\n\r\n{body}");
            let _=tokio::time::timeout(Duration::from_millis(100),stream.write_all(response.as_bytes())).await;
            match result {Some(Reply::Code(code))=>return Ok(code),Some(Reply::Denied)=>return Err("login_denied"),None=>{}}
          }
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    fn req(target: &str) -> Vec<u8> {
        format!("GET {target} HTTP/1.1\r\nHost: 127.0.0.1:12345\r\n\r\n").into_bytes()
    }
    #[test]
    fn accepts_exact_callback_and_matching_state() {
        assert_eq!(
            parse(
                &req("/oauth/callback?code=abc&state=expected"),
                12345,
                "expected",
                "https://accounts.example.org"
            ),
            Some(Reply::Code("abc".into()))
        );
        assert_eq!(
            parse(
                &req("/oauth/callback?error=access_denied&state=expected"),
                12345,
                "expected",
                "https://accounts.example.org"
            ),
            Some(Reply::Denied)
        );
    }
    #[test]
    fn accepts_rfc9207_issuer_parameter() {
        assert_eq!(parse(&req("/oauth/callback?code=abc&state=expected&iss=https%3A%2F%2Faccounts.example.org"),12345,"expected","https://accounts.example.org"),Some(Reply::Code("abc".into())));
    }
    #[test]
    fn rejects_malformed_callbacks_without_consuming_login() {
        for target in [
            "/other?code=abc&state=expected",
            "/oauth/callback?code=abc&state=wrong",
            "/oauth/callback?code=a&code=b&state=expected",
            "/oauth/callback?code=a&state=expected&state=expected",
            "/oauth/callback?code=a&state=expected&error=bad",
            "/oauth/callback?code=%ZZ&state=expected",
            "/oauth/callback?error=access_denied&state=expected&error_description=%FF",
            "/oauth/callback?code=abc&state=expected&iss=https%3A%2F%2Fevil.example.org",
            "/oauth/callback?code=&state=expected",
            "http://127.0.0.1:12345/oauth/callback?code=a&state=expected",
            "/oauth/callback?code=a&state=expected#x",
            "/oauth/callback?code=a&state=expected&extra=x",
        ] {
            assert_eq!(
                parse(
                    &req(target),
                    12345,
                    "expected",
                    "https://accounts.example.org"
                ),
                None,
                "{target}"
            );
        }
        let good = req("/oauth/callback?code=a&state=expected");
        assert_eq!(
            parse(&good, 12346, "expected", "https://accounts.example.org"),
            None
        );
        assert_eq!(
            parse(
                &String::from_utf8(good)
                    .unwrap()
                    .replace("GET ", "POST ")
                    .into_bytes(),
                12345,
                "expected",
                "https://accounts.example.org"
            ),
            None
        );
        assert_eq!(
            parse(
                &vec![b'x'; 8193],
                12345,
                "expected",
                "https://accounts.example.org"
            ),
            None
        );
    }
}
#[cfg(test)]
mod socket_tests {
    use super::*;
    #[tokio::test]
    async fn malformed_request_does_not_consume_real_listener() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let (_tx, rx) = watch::channel(false);
        let task = tokio::spawn(async move {
            receive(
                listener,
                "expected",
                "https://accounts.example.org",
                rx,
                Duration::from_secs(3),
            )
            .await
        });
        for state in ["wrong", "expected"] {
            let mut socket = tokio::net::TcpStream::connect(addr).await.unwrap();
            socket.write_all(format!("GET /oauth/callback?code=abc&state={state} HTTP/1.1\r\nHost: {addr}\r\n\r\n").as_bytes()).await.unwrap();
            let mut response = Vec::new();
            socket.read_to_end(&mut response).await.unwrap();
            let text = std::str::from_utf8(&response).unwrap();
            let (head, body) = text.split_once("\r\n\r\n").unwrap();
            let length = head
                .lines()
                .find_map(|line| line.strip_prefix("Content-Length: "))
                .unwrap()
                .parse::<usize>()
                .unwrap();
            assert_eq!(body.len(), length);
            assert!(std::str::from_utf8(&response)
                .unwrap()
                .starts_with(if state == "wrong" {
                    "HTTP/1.1 400"
                } else {
                    "HTTP/1.1 200"
                }));
        }
        assert_eq!(task.await.unwrap(), Ok("abc".into()));
        assert!(tokio::net::TcpStream::connect(addr).await.is_err());
    }
    #[tokio::test]
    async fn bounded_timeout_and_cancellation_close_listener() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let (_tx, rx) = watch::channel(false);
        assert_eq!(
            receive(
                listener,
                "x",
                "https://accounts.example.org",
                rx,
                Duration::from_millis(5)
            )
            .await,
            Err("login_timeout")
        );
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let (tx, rx) = watch::channel(false);
        let pending = tokio::spawn(async move {
            receive(
                listener,
                "x",
                "https://accounts.example.org",
                rx,
                Duration::from_secs(180),
            )
            .await
        });
        let _socket = tokio::net::TcpStream::connect(addr).await.unwrap();
        tx.send(true).unwrap();
        assert_eq!(
            tokio::time::timeout(Duration::from_millis(100), pending)
                .await
                .unwrap()
                .unwrap(),
            Err("login_cancelled")
        );
    }
}
