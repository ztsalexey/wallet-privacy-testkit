"""Apply only the documented extra-CA change to the locked wallet transport."""

import hashlib
import shutil
import sys
import tomllib
from pathlib import Path


def main():
    lock = Path('/wallet/Cargo.lock')
    original_lock = Path('/wallet/Cargo.original.lock')
    if '--check-lock' in sys.argv:
        before = tomllib.loads(original_lock.read_text())['package']
        after = tomllib.loads(lock.read_text())['package']
        for packages in (before, after):
            for package in packages:
                if package['name'] == 'zingo-netutils' and package['version'] == '5.0.1':
                    package.pop('source', None)
                    package.pop('checksum', None)
        if before != after:
            raise RuntimeError('wallet dependency lock changed beyond the transport path')
        return
    source = next(Path('/usr/local/cargo/registry/src').glob('*/zingo-netutils-5.0.1'))
    target = Path('/wallet/lab-transport')
    shutil.copytree(source, target)
    path = target / 'src/lib.rs'
    if hashlib.sha256(path.read_bytes()).hexdigest() != 'c949503b65c96f7f57b5ca3928cace30f7b743fa0881b573d58b43d0986efea4':
        raise RuntimeError('unexpected transport source')
    needle = '    #[cfg(not(test))]\n    ClientTlsConfig::new().with_webpki_roots()'
    replacement = '''    #[cfg(not(test))]
    {
        let config = ClientTlsConfig::new().with_webpki_roots();
        match std::env::var("ZCASH_LAB_CA") {
            Ok(path) => config.ca_certificate(tonic::transport::Certificate::from_pem(
                std::fs::read(path).expect("read explicitly configured regtest CA"),
            )),
            Err(_) => config,
        }
    }'''
    text = path.read_text()
    if text.count(needle) != 1:
        raise RuntimeError('transport patch context mismatch')
    path.write_text(text.replace(needle, replacement))
    shutil.copyfile(lock, original_lock)
    manifest = Path('/wallet/Cargo.toml')
    text = manifest.read_text()
    if text.count('[patch.crates-io]') != 1:
        raise RuntimeError('unexpected wallet patch table')
    manifest.write_text(text.replace('[patch.crates-io]',
        '[patch.crates-io]\nzingo-netutils = { path = "lab-transport" }'))


if __name__ == '__main__':
    main()
