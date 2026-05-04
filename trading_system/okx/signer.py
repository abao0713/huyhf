import hmac
import hashlib
from datetime import datetime


class BinanceSigner:
    """Binance API签名生成器"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def sign(self, message: str) -> str:
        """生成签名
        :param message: 待签名的消息
        :return: 签名字符串
        """
        mac = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return mac

    def sign_request(self, params: dict) -> str:
        """签名请求参数
        :param params: 请求参数字典
        :return: 签名字符串
        """
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        return self.sign(query_string)

    @staticmethod
    def get_timestamp() -> int:
        """获取当前时间戳（毫秒）
        :return: 时间戳
        """
        return int(datetime.now().timestamp() * 1000)
