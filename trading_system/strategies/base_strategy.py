from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    策略抽象基类

    该类作为所有交易策略的基类，定义了策略的核心接口和通用功能。
    所有具体策略实现必须继承此类并实现其抽象方法。

    设计目的：
        - 提供统一的策略接口规范，确保不同策略遵循相同的调用约定
        - 封装策略共有的属性和方法，如策略名称、交易品种、持仓信息等
        - 定义策略与回测/实盘引擎之间的交互协议

    使用方式：
        1. 创建策略子类，继承BaseStrategy
        2. 实现initialize方法进行策略初始化
        3. 实现on_bar方法处理K线数据并生成交易信号
        4. 实现on_order_update方法处理订单状态更新
        5. 可调用set_params、get_position等方法管理策略参数和持仓

    示例：
        class MyStrategy(BaseStrategy):
            async def initialize(self, symbol: str) -> bool:
                # 策略初始化逻辑
                self.symbol = symbol
                return True

            async def on_bar(self, bar_data: Dict[str, Any]):
                # 生成交易信号
                return {"action": "buy", "quantity": 100}
    """

    def __init__(self, name: str = "BaseStrategy"):
        """
        初始化策略基类

        Args:
            name: 策略名称，用于标识不同的策略实例。
                  在多策略同时运行时，应为每个策略设置唯一的名称以便日志追踪。
                  默认为"BaseStrategy"。
        """
        self.name = name  # 策略名称标识
        self.symbol: str = ""  # 交易品种代码，如"BTCUSDT"、"AAPL"等
        self.position: Dict[str, Any] = {}  # 当前持仓信息，键为持仓方向或品种，值为持仓数量/金额等
        self.params: Dict[str, Any] = {}  # 策略参数字典，用于存储和传递策略的配置参数

    @abstractmethod
    async def initialize(self, symbol: str) -> bool:
        """
        初始化策略

        该方法在策略启动时被调用，用于执行策略初始化相关的操作，
        如加载历史数据、设置指标计算器、配置交易参数等。

        Args:
            symbol: 交易品种代码，指定策略运行的标的。
                    例如股票策略可能传入"600519"（贵州茅台），
                    加密货币策略可能传入"BTCUSDT"。

        Returns:
            bool: 初始化是否成功。
                  返回True表示初始化完成，策略可以正常运行；
                  返回False表示初始化失败，引擎将不会调用on_bar方法。
        """
        pass

    @abstractmethod
    async def on_bar(self, bar_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        K线数据回调，用于生成交易信号

        每当有新的K线数据更新时，引擎会调用此方法。
        策略应在该方法中实现核心的交易逻辑，如技术指标计算、
        信号生成、条件判断等。

        Args:
            bar_data: K线数据字典，包含以下常见字段：
                      - symbol: 品种代码
                      - open: 开盘价
                      - high: 最高价
                      - low: 最低价
                      - close: 收盘价
                      - volume: 成交量
                      - timestamp: 时间戳

        Returns:
            Optional[Dict[str, Any]]: 交易信号字典，如果没有信号则返回None。
                                      交易信号通常包含以下字段：
                                      - action: 交易动作，如"buy"、"sell"、"close"等
                                      - quantity: 交易数量
                                      - price: 交易价格（可选）
                                      - order_type: 订单类型（可选）
        """
        pass

    @abstractmethod
    async def on_order_update(self, order_data: Dict[str, Any]) -> None:
        """
        订单状态更新回调

        当订单状态发生变化时（如订单成交、部分成交、撤销、拒绝等），
        引擎会调用此方法通知策略。策略可以在此方法中更新内部持仓状态、
        记录日志、执行风控检查等操作。

        Args:
            order_data: 订单数据字典，包含以下常见字段：
                        - order_id: 订单ID
                        - symbol: 品种代码
                        - direction: 交易方向（如"buy"、"sell"）
                        - quantity: 订单数量
                        - price: 订单价格
                        - status: 订单状态（如"filled"、"partial_fill"、"cancelled"、"rejected"）
                        - filled_quantity: 已成交数量
                        - timestamp: 更新时间戳
        """
        pass

    def set_params(self, params: Dict[str, Any]) -> None:
        """
        设置策略参数

        用于动态更新策略的配置参数。该方法会将新的参数合并到
        现有的params字典中，不会覆盖整个字典，而是增量更新。

        Args:
            params: 参数字典，包含需要更新的键值对。
                    例如：{"stop_loss": 0.05, "take_profit": 0.10}

        Note:
            该方法会记录参数更新日志，便于排查问题和追踪策略变更。
        """
        self.params.update(params)
        logger.info(f"[{self.name}] 参数更新: {params}")

    def get_position(self) -> Dict[str, Any]:
        """
        获取当前持仓信息

        返回策略当前的持仓状态，供外部系统（如风控模块、绩效计算模块）使用。

        Returns:
            Dict[str, Any]: 持仓信息字典，通常包含：
                            - direction: 持仓方向（如"long"、"short"、"neutral"）
                            - quantity: 持仓数量
                            - entry_price: 开仓价格
                            - current_price: 当前价格（可选）
                            - unrealized_pnl: 浮动盈亏（可选）
        """
        return self.position

    def update_position(self, position: Dict[str, Any]) -> None:
        """
        更新持仓信息

        当收到订单成交回报或需要同步外部持仓数据时，调用此方法更新
        策略内部的持仓状态。

        Args:
            position: 新的持仓信息字典，格式同get_position返回值。
                      例如：{"direction": "long", "quantity": 100, "entry_price": 50000}
        """
        self.position = position