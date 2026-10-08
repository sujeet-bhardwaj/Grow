"""
Order Execution Router for Futures & Options (F&O)
Routes option orders to Paper Trading Simulator or Groww Live F&O API.
"""

import config
from paper_trader import PaperTrader


class ExecutionManager:
    def __init__(self, access_token: str, paper_trader: PaperTrader):
        self.access_token = access_token
        self.paper_trader = paper_trader
        self.groww_client = None
        self._init_client()

    def _init_client(self):
        if self.access_token and self.access_token != "SIMULATED_GROWW_TOKEN":
            try:
                from growwapi import GrowwAPI
                self.groww_client = GrowwAPI(self.access_token)
            except Exception as e:
                self.groww_client = None

    def place_option_order(
        self,
        contract_symbol: str,
        underlying: str,
        strike: int,
        option_type: str,
        lots: int,
        quantity: int,
        premium: float,
        sl_premium: float,
        tp_premium: float,
        entry_spot: float = 0.0,
        target_index_pts: float = 12.5,
        sl_index_pts: float = 6.0,
        breakeven_trigger: float = 0.0,
        confluence_score: int = 0
    ) -> bool:
        """
        Executes NIFTY Scalp Option Order (BUY CE or BUY PE).
        """
        if config.TRADING_MODE == "PAPER":
            return self.paper_trader.open_trade(
                contract_symbol=contract_symbol,
                underlying=underlying,
                strike=strike,
                option_type=option_type,
                lots=lots,
                quantity=quantity,
                premium=premium,
                sl_premium=sl_premium,
                tp_premium=tp_premium,
                entry_spot=entry_spot,
                target_index_pts=target_index_pts,
                sl_index_pts=sl_index_pts,
                breakeven_trigger=breakeven_trigger,
                confluence_score=confluence_score
            )

        # ----------------------------------------------------------------------
        # LIVE GROWW F&O API EXECUTION
        # ----------------------------------------------------------------------
        print(f"\n[LIVE F&O ORDER] >>> Sending BUY {lots} Lots ({quantity} Qty) of {contract_symbol} to Groww F&O...")

        if not self.groww_client:
            self._init_client()

        if self.groww_client:
            try:
                from growwapi import GrowwAPI
                order_response = self.groww_client.place_order(
                    validity=GrowwAPI.VALIDITY_DAY,
                    exchange=GrowwAPI.EXCHANGE_NSE,
                    order_type=GrowwAPI.ORDER_TYPE_MARKET,
                    product=GrowwAPI.PRODUCT_MIS,
                    quantity=int(quantity),
                    segment=GrowwAPI.SEGMENT_FNO,
                    trading_symbol=contract_symbol,
                    transaction_type=GrowwAPI.TRANSACTION_TYPE_BUY,
                    price=0.0
                )
                print(f"[LIVE F&O ORDER SUCCESS] Groww Response: {order_response}")
                return True
            except Exception as e:
                print(f"[LIVE F&O ORDER ERROR] {e}")
                return False

        print("[LIVE F&O ERROR] Groww client not connected.")
        return False

    def close_option_order(self, contract_symbol: str, current_premium: float, reason: str, quantity: int = 25) -> bool:
        """Squares off F&O option position."""
        if config.TRADING_MODE == "PAPER":
            closed = self.paper_trader.close_trade(contract_symbol, current_premium, reason)
            return bool(closed)

        print(f"\n[LIVE F&O EXIT] Closing live option position for {contract_symbol} due to: {reason}")
        if self.groww_client:
            try:
                from growwapi import GrowwAPI
                order_response = self.groww_client.place_order(
                    validity=GrowwAPI.VALIDITY_DAY,
                    exchange=GrowwAPI.EXCHANGE_NSE,
                    order_type=GrowwAPI.ORDER_TYPE_MARKET,
                    product=GrowwAPI.PRODUCT_MIS,
                    quantity=int(quantity),
                    segment=GrowwAPI.SEGMENT_FNO,
                    trading_symbol=contract_symbol,
                    transaction_type=GrowwAPI.TRANSACTION_TYPE_SELL,
                    price=0.0
                )
                print(f"[LIVE F&O EXIT EXECUTED] Response: {order_response}")
                return True
            except Exception as e:
                print(f"[LIVE F&O EXIT ERROR] {e}")
                return False

        return True
