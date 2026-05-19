import base64
import hashlib
import hmac
import os
from datetime import datetime
from typing import Dict, Optional, Tuple, Union
from urllib.parse import quote, urlencode


class BinanceSigner:
    """Binance API签名生成器"""

    def __init__(self, secret_key: str = "", private_key: str = None, private_key_passphrase: str = None):
        self.secret_key = secret_key or ""
        self.private_key = private_key
        self.private_key_passphrase = private_key_passphrase
        self._asymmetric_signer = None

        if self.private_key:
            self._asymmetric_signer = Signers.get_signer(self.private_key, self.private_key_passphrase)

    def sign(self, message: str) -> str:
        message_bytes = message.encode("utf-8")

        if self._asymmetric_signer is not None:
            try:
                from Crypto.Hash import SHA256
            except Exception as e:
                raise ImportError("使用 RSA/Ed25519 私钥签名需要安装 pycryptodome") from e

            if hasattr(self._asymmetric_signer, "sign"):
                if self._asymmetric_signer.__class__.__name__ == "PKCS115_SigScheme":
                    signature_bytes = self._asymmetric_signer.sign(SHA256.new(message_bytes))
                else:
                    signature_bytes = self._asymmetric_signer.sign(message_bytes)

                raw_signature = base64.b64encode(signature_bytes).decode("utf-8")
                return quote(raw_signature, safe="")

            raise ValueError("Signer object does not support sign()")

        mac = hmac.new(self.secret_key.encode("utf-8"), message_bytes, hashlib.sha256).hexdigest()
        return mac

    def sign_request(self, params: dict) -> str:
        query_string = BinanceSigner.build_query_string(params)
        return self.sign(query_string)

    @staticmethod
    def get_timestamp() -> int:
        """获取当前时间戳（毫秒）
        :return: 时间戳
        """
        return int(datetime.now().timestamp() * 1000)

    @staticmethod
    def build_query_string(params: dict) -> str:
        return urlencode(params, doseq=True, quote_via=quote, safe="-_.~")


class Signers:
    _rsa_keys: Dict[Tuple[str, Optional[str]], "RSA.RsaKey"] = {}
    _rsa_signers: Dict[Tuple[str, Optional[str]], "pkcs1_15.PKCS115_SigScheme"] = {}

    _ed25519_keys: Dict[Tuple[str, Optional[str]], "ECC.EccKey"] = {}
    _ed25519_signers: Dict[Tuple[str, Optional[str]], object] = {}

    @staticmethod
    def _load_private_key_data(key_input: str) -> str:
        if os.path.exists(key_input):
            with open(key_input, "r") as f:
                return f.read()
        return key_input

    @classmethod
    def get_rsa_key(cls, key: str, passphrase: Optional[str]):
        try:
            from Crypto.PublicKey import RSA
        except Exception as e:
            raise ImportError("使用 RSA/Ed25519 私钥签名需要安装 pycryptodome") from e

        key_data = cls._load_private_key_data(key)
        cache_key = (key_data, passphrase)
        if cache_key not in cls._rsa_keys:
            cls._rsa_keys[cache_key] = RSA.import_key(key_data, passphrase=passphrase)
        return cls._rsa_keys[cache_key]

    @classmethod
    def get_rsa_signer(cls, key: str, passphrase: Optional[str]):
        try:
            from Crypto.Signature import pkcs1_15
        except Exception as e:
            raise ImportError("使用 RSA/Ed25519 私钥签名需要安装 pycryptodome") from e

        cache_key = (cls._load_private_key_data(key), passphrase)
        if cache_key not in cls._rsa_signers:
            rsa_key = cls.get_rsa_key(key, passphrase)
            cls._rsa_signers[cache_key] = pkcs1_15.new(rsa_key)
        return cls._rsa_signers[cache_key]

    @classmethod
    def clear_rsa_cache(cls):
        cls._rsa_keys.clear()
        cls._rsa_signers.clear()

    @classmethod
    def get_ed25519_key(cls, key: str, passphrase: Optional[str]):
        try:
            from Crypto.PublicKey import ECC
        except Exception as e:
            raise ImportError("使用 RSA/Ed25519 私钥签名需要安装 pycryptodome") from e

        key_data = cls._load_private_key_data(key)
        cache_key = (key_data, passphrase)
        if cache_key not in cls._ed25519_keys:
            cls._ed25519_keys[cache_key] = ECC.import_key(key_data, passphrase=passphrase)
        return cls._ed25519_keys[cache_key]

    @classmethod
    def get_ed25519_signer(cls, key: str, passphrase: Optional[str]):
        try:
            from Crypto.Signature import eddsa
        except Exception as e:
            raise ImportError("使用 RSA/Ed25519 私钥签名需要安装 pycryptodome") from e

        cache_key = (cls._load_private_key_data(key), passphrase)
        if cache_key not in cls._ed25519_signers:
            ed_key = cls.get_ed25519_key(key, passphrase)
            cls._ed25519_signers[cache_key] = eddsa.new(ed_key, "rfc8032")
        return cls._ed25519_signers[cache_key]

    @classmethod
    def clear_ed25519_cache(cls):
        cls._ed25519_keys.clear()
        cls._ed25519_signers.clear()

    @classmethod
    def get_signer(cls, private_key: str, passphrase: Optional[str] = None):
        try:
            return cls.get_rsa_signer(private_key, passphrase)
        except (ValueError, IndexError, TypeError):
            pass

        try:
            return cls.get_ed25519_signer(private_key, passphrase)
        except (ValueError, IndexError, TypeError):
            pass

        raise ValueError("Unsupported or invalid private key format. Private key must be either 'RSA' or 'ED25519'")
