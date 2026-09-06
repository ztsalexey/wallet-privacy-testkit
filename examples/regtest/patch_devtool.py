"""Opt-in lab CA for the pinned independent development wallet; retain TLS verification."""
import hashlib
from pathlib import Path

path = Path('/devtool/src/remote.rs')
source = path.read_text()
if hashlib.sha256(path.read_bytes()).hexdigest() != '7548ba3529d49c600a0b1a732ced084e78b8fd43fde761edaa40e09bc158fd40':
    raise RuntimeError('unexpected devtool transport source')
source = source.replace('fn use_tls(&self) -> bool {', '''fn use_tls(&self) -> bool {
        if std::env::var_os("ZCASH_LAB_CA").is_some() { return true; }''', 1)
source = source.replace('let tls = ClientTlsConfig::new()', 'let mut tls = ClientTlsConfig::new()', 1)
source = source.replace('            channel.tls_config(tls)?', '''            if let Some(path) = std::env::var_os("ZCASH_LAB_CA") {
                tls = tls.ca_certificate(tonic::transport::Certificate::from_pem(std::fs::read(path)?));
            }
            channel.tls_config(tls)?''', 1)
path.write_text(source)
