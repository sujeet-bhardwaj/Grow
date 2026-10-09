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

    def emergency_square_off_all(self, reason: str = "EMERGENCY KILL SWITCH ACTIVATED") -> dict:
        """
        Immediately squares off all active positions across Paper and Live Groww broker
        per PDF Section 7, 8 & 14 (Kill switch / protective emergency exit).
        """
        results = {"paper_closed": 0, "live_closed": 0, "errors": []}

        # 1. Square off all open Paper positions
        open_syms = list(self.paper_trader.open_positions.keys())
        for sym in open_syms:
            pos = self.paper_trader.open_positions.get(sym)
            if pos:
                curr_p = pos.get("current_price", pos.get("entry_price", 100.0))
                self.paper_trader.close_trade(sym, curr_p, f"KILL SWITCH: {reason}")
                results["paper_closed"] += 1

        # 2. Square off any active Live Groww positions
        if config.TRADING_MODE == "LIVE" and self.groww_client:
            try:
                from growwapi import GrowwAPI
                pos_res = self.groww_client.get_positions_for_user()
                if isinstance(pos_res, dict):
                    positions = pos_res.get("positions", [])
                    for p in positions:
                        net_qty = int(p.get("net_quantity", 0) or 0)
                        sym = p.get("trading_symbol", "")
                        if net_qty > 0 and sym:
                            self.close_option_order(sym, 0.0, f"KILL SWITCH EMERGENCY: {reason}", quantity=net_qty)
                            results["live_closed"] += 1
            except Exception as e:
                err_str = str(e)
                results["errors"].append(err_str)
                print(f"[KILL SWITCH LIVE EXIT ERROR] {err_str}")

        print(f"[EMERGENCY SQUARED OFF] Completed: {results['paper_closed']} Paper, {results['live_closed']} Live positions closed.")
        return results

