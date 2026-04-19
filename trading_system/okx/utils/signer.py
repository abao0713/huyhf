import time
import hmac
import base64
from hashlib import sha256


def get_timestamp() -> str:
    """获取Unix时间戳（秒）"""
    return str(int(time.time()))


def get_timestamp_ms() -> str:
    """获取Unix时间戳（毫秒）"""
    return str(int(time.time() * 1000))


def generate_sign(timestamp: str, secret_key: str, method: str, request_path: str, body: str = "") -> str:
    """
    生成签名字符串
    算法：HMAC SHA256(timestamp + method + request_path + body, secret_key)
    
    :param timestamp: 时间戳（秒）
    :param secret_key: 密钥
    :param method: HTTP方法（GET, POST, PUT, DELETE）
    :param request_path: 请求路径
    :param body: 请求体（GET请求为空字符串）
    :return: 签名字符串
    """
    message = timestamp + method + request_path + body
    
    # 使用HMAC SHA256加密
    h = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), sha256)
    # 进行Base64编码
    signature = base64.b64encode(h.digest()).decode('utf-8')
    
    return signature
