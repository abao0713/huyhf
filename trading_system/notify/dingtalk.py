import hashlib
import hmac
import base64
import time
import urllib.parse
import urllib.request
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def mask_secret(value: str, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    """对敏感信息进行脱敏处理

    Args:
        value: 原始字符串
        visible_prefix: 保留前缀字符数
        visible_suffix: 保留后缀字符数

    Returns:
        脱敏后的字符串，如 "abcd****efgh"
    """
    if not value:
        return "***"
    if len(value) <= visible_prefix + visible_suffix:
        return "***"
    return f"{value[:visible_prefix]}{'*' * (len(value) - visible_prefix - visible_suffix)}{value[-visible_suffix:]}"


class DingTalkNotifier:
    """钉钉自定义机器人消息通知（签名认证）"""

    WEBHOOK_BASE_URL = "https://oapi.dingtalk.com/robot/send"
    MAX_MSG_PER_MINUTE = 18

    def __init__(self, access_token: str = None, secret: str = None, env_info: str = "生产环境"):
        """初始化钉钉通知器
        
        Args:
            access_token: 钉钉机器人访问令牌
            secret: 钉钉机器人签名密钥
            env_info: 环境信息，用于消息页脚显示，默认为"生产环境"
        """
        if not access_token or not secret:
            raise ValueError("access_token 和 secret 不能为空")

        self.access_token = access_token
        self.secret = secret
        self.env_info = env_info
        self._send_times = []
        
        # 记录初始化日志（脱敏）
        logger.info(f"[DingTalk] 通知器初始化完成，access_token: {mask_secret(access_token)}")

    @staticmethod
    def _now_str():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _build_footer(self) -> str:
        """构建消息页脚"""
        return f"\n\n---\n*节点: {self.env_info} | 时间: {self._now_str()}*"

    @staticmethod
    def _truncate_msg(msg: str, max_len: int = 50) -> str:
        """截断过长的错误信息"""
        if not msg:
            return "N/A"
        if len(msg) > max_len:
            return msg[:max_len] + "..."
        return msg

    @staticmethod
    def _get_error_suggestions(error_code) -> list:
        """根据错误码返回排查建议列表"""
        error_map = {
            "-1021": [
                "离线环境时间漂移，请手动校准系统时间至北京时间",
                "在代码中引入服务器时间动态校准逻辑",
                "检查系统NTP服务是否正常运行",
            ],
            "-1109": [
                "API Key与环境不匹配，请检查base_path配置",
                "确认Key在对应环境(testnet/demo/正式)创建",
                "检查是否使用了正确环境的API密钥",
            ],
            "-2015": [
                "API Key权限不足，请检查是否勾选'Futures Trading'权限",
                "登录币安官网重新配置API Key权限",
                "确认API Key未被禁用或过期",
            ],
            "-2019": [
                "保证金不足，请检查账户可用余额",
                "降低杠杆倍数或减少仓位规模",
                "充值或调整资金管理策略",
            ],
            "-2022": [
                "订单价格超出允许范围，请检查价格合理性",
                "参考当前市场价格重新设置订单价格",
                "检查交易对的PRICE_FILTER限制",
            ],
        }
        code_str = str(error_code) if error_code is not None else ""
        if code_str in error_map:
            return error_map[code_str]
        return [
            "检查网络连接是否正常",
            "核对请求参数格式是否正确",
            "查阅币安API文档确认接口要求",
        ]

    def _generate_sign(self):
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode("utf-8")
        string_to_sign = f"{timestamp}\n{self.secret}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def _build_url(self):
        timestamp, sign = self._generate_sign()
        return f"{self.WEBHOOK_BASE_URL}?access_token={self.access_token}&timestamp={timestamp}&sign={sign}"

    def _check_rate_limit(self):
        now = time.time()
        self._send_times = [t for t in self._send_times if now - t < 60]
        if len(self._send_times) >= self.MAX_MSG_PER_MINUTE:
            logger.warning("[DingTalk] 频率限制: 1分钟内已发送%s条，跳过", len(self._send_times))
            return False
        self._send_times.append(now)
        return True

    def _send(self, payload: dict) -> bool:
        if not self._check_rate_limit():
            return False
        try:
            url = self._build_url()
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("errcode") == 0:
                    logger.info("[DingTalk] 消息发送成功")
                    return True
                else:
                    logger.error("[DingTalk] 发送失败: %s", result)
                    return False
        except Exception as e:
            logger.error("[DingTalk] 发送异常: %s", e)
            return False

    def send_text(self, content: str) -> bool:
        payload = {
            "msgtype": "text",
            "text": {"content": content},
        }
        return self._send(payload)

    def send_markdown(self, title: str, text: str) -> bool:
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        }
        return self._send(payload)

    def send_trade_signal(self, signal: dict, symbol: str = "") -> bool:
        action = signal.get("action", "")
        reason = signal.get("reason", "")
        ratio = signal.get("position_ratio", 0)
        entry = signal.get("entry_price", signal.get("stop_loss", ""))
        stop_loss = signal.get("stop_loss", "")
        action_map = {
            "EARLY_LONG_ENTRY": "🔴 做多入场信号（提前）",
            "EARLY_SHORT_ENTRY": "🟢 做空入场信号（提前）",
            "LONG_PROBE": "🔴 做多入场信号（试探）",
            "SHORT_PROBE": "🟢 做空入场信号（试探）",
            "LONG_CONFIRM": "🔴 做多加仓信号",
            "SHORT_CONFIRM": "🟢 做空加仓信号",
            "CLOSE_LONG": "✅ 平多信号",
            "CLOSE_SHORT": "✅ 平空信号",
            "STOP_LOSS": "⚠️ 止损信号",
        }
        title_text = action_map.get(action, "📊 交易信号")

        text = f"### 📈 币安合约交易信号\n\n"
        text += f"> **状态**: 📊 **{title_text}**\n\n"
        text += f"**🔹 交易参数**\n"
        text += f"- 交易对: `{symbol}`\n"
        text += f"- 信号类型: `{action}`\n"
        text += f"- 仓位比例: `{ratio*100:.0f}%`\n"
        if entry:
            text += f"- 入场价: `{entry}`\n"
        if stop_loss:
            text += f"- 止损价: `{stop_loss}`\n"
        text += f"\n**🔸 信号详情**\n"
        text += f"- 原因: {reason}\n"
        text += self._build_footer()

        return self.send_markdown(title_text, text)

    def send_order_result(self, action: str, result: dict, symbol: str = "") -> bool:
        """发送订单结果通知，采用标准交易通知格式"""
        status = result.get("status", "")
        side = result.get("side", "")
        order_type = result.get("type", result.get("order_type", ""))
        qty = result.get("origQty", result.get("executedQty", result.get("quantity", 0)))
        price = result.get("price", result.get("avgPrice", "0"))
        order_id = result.get("orderId", result.get("order_id", ""))
        error_msg = result.get("error", result.get("msg", ""))
        error_code = result.get("error_code", result.get("code", ""))

        # 判断成功/失败
        is_failed = bool(error_msg)

        if is_failed:
            # 失败场景
            status_icon = "❌"
            status_text = "下单失败"
            title = "❌ 订单失败"

            # 提取错误码
            if not error_code and error_msg:
                # 尝试从错误信息中提取错误码
                import re
                match = re.search(r'\((-?\d+),', str(error_msg))
                if match:
                    error_code = match.group(1)

            # 构建消息
            text = f"### 📈 币安合约交易信号\n\n"
            text += f"> **状态**: {status_icon} **{status_text}**\n\n"
            text += f"**🔹 交易参数**\n"
            text += f"- 交易对: `{symbol}`\n"
            text += f"- 方向: `{side}`\n"
            text += f"- 类型: `{order_type}`\n"
            text += f"- 数量: `{qty}`\n"
            text += f"- 价格: `{price if order_type != 'MARKET' else '市价'}`\n\n"
            text += f"**🔸 返回详情**\n"
            text += f"- 错误码: `{error_code or 'N/A'}`\n"
            text += f"- 错误信息: `{self._truncate_msg(str(error_msg))}`\n"
            text += f"- 订单ID: `None`\n\n"
            text += f"**💡 排查建议**\n"
            suggestions = self._get_error_suggestions(error_code)
            for i, s in enumerate(suggestions, 1):
                text += f"{i}. {s}\n"
            text += self._build_footer()
        else:
            # 成功场景
            if status == "NEW":
                status_icon = "✅"
                status_text = "已挂单"
            elif status == "FILLED":
                status_icon = "✅"
                status_text = "已成交"
            elif status == "PARTIALLY_FILLED":
                status_icon = "⚠️"
                status_text = "部分成交"
            else:
                status_icon = "✅"
                status_text = status or "下单成功"

            title = "📋 订单结果"
            text = f"### 📈 币安合约交易信号\n\n"
            text += f"> **状态**: {status_icon} **{status_text}**\n\n"
            text += f"**🔹 交易参数**\n"
            text += f"- 交易对: `{symbol}`\n"
            text += f"- 方向: `{side}`\n"
            text += f"- 类型: `{order_type}`\n"
            text += f"- 数量: `{qty}`\n"
            text += f"- 价格: `{price if order_type != 'MARKET' else '市价'}`\n\n"
            text += f"**🔸 返回详情**\n"
            text += f"- 错误码: `N/A`\n"
            text += f"- 错误信息: `N/A`\n"
            text += f"- 订单ID: `{order_id}`\n\n"
            text += f"**💡 排查建议**\n"
            text += f"无\n"
            text += self._build_footer()

        return self.send_markdown(title, text)

    def send_error(self, error_msg: str, symbol: str = "") -> bool:
        """发送运行异常通知，包含排查建议"""
        # 尝试提取错误码
        import re
        error_code = ""
        match = re.search(r'\((-?\d+),', str(error_msg))
        if match:
            error_code = match.group(1)

        text = f"### 📈 币安合约交易信号\n\n"
        text += f"> **状态**: ❌ **运行异常**\n\n"
        text += f"**🔹 基本信息**\n"
        text += f"- 交易对: `{symbol or 'N/A'}`\n\n"
        text += f"**🔸 错误详情**\n"
        text += f"- 错误码: `{error_code or 'N/A'}`\n"
        text += f"- 错误信息: `{self._truncate_msg(str(error_msg))}`\n\n"
        text += f"**💡 排查建议**\n"
        suggestions = self._get_error_suggestions(error_code)
        for i, s in enumerate(suggestions, 1):
            text += f"{i}. {s}\n"
        text += self._build_footer()

        return self.send_markdown("❌ 运行异常", text)

    def send_status(self, status_type: str, info: dict = None) -> bool:
        """发送状态通知（策略启动/停止/风控警告）"""
        info = info or {}
        
        if status_type == "started":
            title = "🚀 策略启动"
            text = f"### 📈 币安合约交易信号\n\n"
            text += f"> **状态**: 🚀 **策略启动**\n\n"
            text += f"**🔹 策略配置**\n"
            text += f"- 交易对: `{info.get('symbol', '')}`\n"
            text += f"- 模式: `{info.get('mode', '')}`\n"
            text += f"- 杠杆: `{info.get('leverage', '')}x`\n\n"
            text += f"**🔸 关键位**\n"
            text += f"- 支撑位: `{info.get('support_levels', '')}`\n"
            text += f"- 阻力位: `{info.get('resistance_levels', '')}`\n"
            text += self._build_footer()
            
        elif status_type == "stopped":
            title = "🛑 策略停止"
            text = f"### 📈 币安合约交易信号\n\n"
            text += f"> **状态**: 🛑 **策略停止**\n\n"
            text += f"**🔹 策略信息**\n"
            text += f"- 交易对: `{info.get('symbol', '')}`\n\n"
            text += f"**🔸 运行统计**\n"
            text += f"- 总交易次数: `{info.get('total_trades', 0)}`\n"
            text += f"- 当前盈亏: `{info.get('pnl', '')}`\n"
            text += self._build_footer()
            
        elif status_type == "risk_warning":
            title = "⚠️ 风控警告"
            text = f"### 📈 币安合约交易信号\n\n"
            text += f"> **状态**: ⚠️ **风控警告**\n\n"
            text += f"**🔹 风控信息**\n"
            text += f"- 交易对: `{info.get('symbol', '')}`\n\n"
            text += f"**🔸 风险指标**\n"
            text += f"- 连续止损: `{info.get('consecutive_stops', 0)}次`\n"
            text += f"- 日亏损: `{info.get('daily_loss_pct', 0)*100:.1f}%`\n"
            text += f"- 暂停交易: `{'是' if info.get('trading_paused', False) else '否'}`\n"
            text += self._build_footer()
        else:
            return False
            
        return self.send_markdown(title, text)