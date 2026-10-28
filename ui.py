"""
Trading Journal UI
Institutional-grade Dark Theme Dashboard built with Pygame.
Features interactive charts, position sizing calculator, real-time trade logging, and modal dialogs.
"""

import pygame
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from models import Trade, TradeType, TradeStatus, AssetClass
from services import TradeService
from calculators import TradingCalculator


class TextInput:
    """Interactive text input field with cursor, focus, and backspace handling"""
    def __init__(self, rect: pygame.Rect, placeholder: str = "", default_text: str = ""):
        self.rect = rect
        self.placeholder = placeholder
        self.text = default_text
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle mouse click and keyboard input. Returns True if value changed."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            return False

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                return False
            else:
                if len(event.unicode) > 0 and event.unicode.isprintable():
                    self.text += event.unicode
                    return True
        return False

    def update(self, dt: int):
        self.cursor_timer += dt
        if self.cursor_timer >= 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, colors: dict):
        # Background
        bg_col = colors["INPUT_BG"] if not self.active else colors["INPUT_BG_ACTIVE"]
        pygame.draw.rect(surface, bg_col, self.rect, border_radius=4)
        
        # Border
        border_col = colors["BLUE"] if self.active else colors["BORDER"]
        pygame.draw.rect(surface, border_col, self.rect, width=1, border_radius=4)

        # Text / Placeholder
        display_str = self.text if self.text else self.placeholder
        text_col = colors["TEXT_MAIN"] if self.text else colors["TEXT_MUTED"]
        
        # Truncate if overflowing width
        txt_surf = font.render(display_str, True, text_col)
        # Position text with 8px left margin
        text_y = self.rect.y + (self.rect.height - txt_surf.get_height()) // 2
        surface.blit(txt_surf, (self.rect.x + 8, text_y))

        # Blinking cursor
        if self.active and self.cursor_visible:
            actual_text_width = font.size(self.text)[0] if self.text else 0
            cursor_x = self.rect.x + 8 + actual_text_width
            if cursor_x < self.rect.right - 4:
                pygame.draw.line(surface, colors["TEXT_MAIN"], (cursor_x, text_y + 2), (cursor_x, text_y + txt_surf.get_height() - 2), 2)


class TradingJournalUI:
    """Professional Trading Journal Application Interface"""

    def __init__(self, service: TradeService):
        self.service = service
        self.screen_width = 1240
        self.screen_height = 800
        self.running = False
        self.current_tab = "dashboard"  # "dashboard", "trades", "add_trade", "analytics", "calculator"
        
        # Toast notification system
        self.toast_message = ""
        self.toast_timer = 0
        self.toast_color = (14, 203, 129)

        # Modal state
        self.active_modal: Optional[str] = None  # None, "close_trade", "trade_detail"
        self.modal_trade: Optional[Trade] = None
        self.modal_exit_price_input: Optional[TextInput] = None

        # Filter state for trades tab
        self.trades_filter = "ALL"  # "ALL", "OPEN", "CLOSED"
        self.trades_search = ""
        self.trades_page = 0
        self.trades_per_page = 11

        # Colors - Refined Bloomberg Dark Theme
        self.colors = {
            "BG": (19, 23, 34),
            "CARD_BG": (30, 34, 45),
            "CARD_HOVER": (38, 43, 56),
            "HEADER_BG": (24, 28, 39),
            "BORDER": (42, 46, 57),
            "BORDER_LIGHT": (55, 60, 75),
            "TEXT_MAIN": (234, 236, 239),
            "TEXT_MUTED": (120, 123, 134),
            "TEXT_FAINT": (80, 84, 96),
            "GREEN": (14, 203, 129),
            "GREEN_BG": (20, 50, 40),
            "RED": (246, 70, 93),
            "RED_BG": (55, 25, 30),
            "BLUE": (41, 98, 255),
            "BLUE_HOVER": (65, 115, 255),
            "GOLD": (240, 185, 11),
            "INPUT_BG": (24, 28, 39),
            "INPUT_BG_ACTIVE": (28, 33, 46)
        }

        self.init_pygame()
        self.init_forms()

    def init_pygame(self):
        """Initialize Pygame display, fonts, and clock"""
        pygame.init()
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Trading Journal Pro - Quantitative Portfolio Analytics")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_title = pygame.font.SysFont("Segoe UI, Roboto, Arial", 22, bold=True)
        self.font_header = pygame.font.SysFont("Segoe UI, Roboto, Arial", 16, bold=True)
        self.font_body = pygame.font.SysFont("Segoe UI, Roboto, Arial", 14)
        self.font_bold = pygame.font.SysFont("Segoe UI, Roboto, Arial", 14, bold=True)
        self.font_small = pygame.font.SysFont("Segoe UI, Roboto, Arial", 12)
        self.font_kpi_value = pygame.font.SysFont("Segoe UI, Roboto, Arial", 26, bold=True)

    def init_forms(self):
        """Initialize interactive form inputs"""
        # Add Trade Form Fields
        self.add_inputs = {
            "symbol": TextInput(pygame.Rect(180, 120, 200, 32), placeholder="e.g. NVDA, EURUSD"),
            "trade_type": TextInput(pygame.Rect(180, 165, 200, 32), default_text="BUY"),
            "asset_class": TextInput(pygame.Rect(180, 210, 200, 32), default_text="STOCKS"),
            "quantity": TextInput(pygame.Rect(180, 255, 200, 32), placeholder="e.g. 50"),
            "entry_price": TextInput(pygame.Rect(180, 300, 200, 32), placeholder="e.g. 120.50"),
            "stop_loss": TextInput(pygame.Rect(560, 120, 200, 32), placeholder="e.g. 115.00"),
            "take_profit": TextInput(pygame.Rect(560, 165, 200, 32), placeholder="e.g. 135.00"),
            "commission": TextInput(pygame.Rect(560, 210, 200, 32), default_text="0.0"),
            "setup": TextInput(pygame.Rect(560, 255, 200, 32), default_text="Breakout"),
            "notes": TextInput(pygame.Rect(180, 350, 580, 32), placeholder="Catalyst, confluence, mental state...")
        }

        # Position Size Calculator Fields
        self.calc_inputs = {
            "account_size": TextInput(pygame.Rect(240, 140, 220, 34), default_text="10000"),
            "risk_pct": TextInput(pygame.Rect(240, 190, 220, 34), default_text="1.0"),
            "entry_price": TextInput(pygame.Rect(240, 240, 220, 34), default_text="150.00"),
            "stop_loss": TextInput(pygame.Rect(240, 290, 220, 34), default_text="145.00")
        }

        # Search box for trades list
        self.search_input = TextInput(pygame.Rect(960, 85, 220, 30), placeholder="Search symbol...")

    def trigger_toast(self, message: str, is_error: bool = False):
        """Display a temporary toast notification"""
        self.toast_message = message
        self.toast_timer = 200
        self.toast_color = self.colors["RED"] if is_error else self.colors["GREEN"]

    def run(self):
        """Main application UI loop"""
        self.running = True
        while self.running:
            dt = self.clock.tick(60)
            self.handle_events()
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    def update(self, dt: int):
        """Update timers and animated elements"""
        if self.toast_timer > 0:
            self.toast_timer -= 1

        # Update input cursors
        if self.current_tab == "add_trade":
            for inp in self.add_inputs.values():
                inp.update(dt)
        elif self.current_tab == "calculator":
            for inp in self.calc_inputs.values():
                inp.update(dt)
        elif self.current_tab == "trades":
            self.search_input.update(dt)

        if self.modal_exit_price_input:
            self.modal_exit_price_input.update(dt)

    def handle_events(self):
        """Handle user inputs, clicks, and keystrokes"""
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            # If modal is open, modal intercepts clicks
            if self.active_modal:
                self.handle_modal_events(event)
                continue

            # Forward to inputs depending on tab
            if self.current_tab == "add_trade":
                for inp in self.add_inputs.values():
                    inp.handle_event(event)
            elif self.current_tab == "calculator":
                for inp in self.calc_inputs.values():
                    inp.handle_event(event)
            elif self.current_tab == "trades":
                if self.search_input.handle_event(event):
                    self.trades_page = 0

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_mouse_click(mouse_pos)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.active_modal = None

    def handle_mouse_click(self, pos: Tuple[int, int]):
        """Handle clicks on tabs, buttons, and rows"""
        x, y = pos

        # 1. Navigation Bar Clicks (y in 0..55)
        if 0 <= y <= 55:
            tabs = [
                ("dashboard", 220, 320),
                ("trades", 330, 410),
                ("add_trade", 420, 520),
                ("analytics", 530, 620),
                ("calculator", 630, 740)
            ]
            for tab_name, x1, x2 in tabs:
                if x1 <= x <= x2:
                    self.current_tab = tab_name
                    return

            # Quick action buttons on right side of navbar
            if 1000 <= x <= 1100 and 12 <= y <= 42:
                # Export CSV
                count = self.service.export_csv("trades_export.csv")
                self.trigger_toast(f"Exported {count} trades to trades_export.csv")
                return
            elif 1115 <= x <= 1220 and 12 <= y <= 42:
                # Seed Samples
                self.service.seed_sample_data(clear_first=False)
                self.trigger_toast("Sample trades loaded successfully!")
                return

        # 2. Tab Specific Clicks
        if self.current_tab == "dashboard":
            # Click on "Add Trade" shortcut button if any
            pass

        elif self.current_tab == "trades":
            # Filter pills: ALL (x: 40..100), OPEN (110..180), CLOSED (190..270)
            if 80 <= y <= 112:
                if 40 <= x <= 100:
                    self.trades_filter = "ALL"
                    self.trades_page = 0
                elif 110 <= x <= 180:
                    self.trades_filter = "OPEN"
                    self.trades_page = 0
                elif 190 <= x <= 270:
                    self.trades_filter = "CLOSED"
                    self.trades_page = 0

            # Pagination buttons
            if self.screen_height - 50 <= y <= self.screen_height - 20:
                if 40 <= x <= 120 and self.trades_page > 0:
                    self.trades_page -= 1
                elif 130 <= x <= 210:
                    self.trades_page += 1

            # Trade table row click (to view detail or close)
            # Headers start at y=125, rows start at 160, row_height=42
            row_y = 160
            trades = self.get_filtered_trades()
            start_idx = self.trades_page * self.trades_per_page
            visible_trades = trades[start_idx:start_idx + self.trades_per_page]

            for i, trade in enumerate(visible_trades):
                curr_y = row_y + i * 42
                if curr_y <= y <= curr_y + 38:
                    # Check if clicked "Close" button (x: 1090..1160)
                    if trade.is_open and 1090 <= x <= 1160:
                        self.open_close_modal(trade)
                    elif 1170 <= x <= 1210:
                        # Delete button
                        self.service.delete_trade(trade.id)
                        self.trigger_toast(f"Deleted {trade.id}")
                    else:
                        # Open detail modal
                        self.open_detail_modal(trade)
                    break

        elif self.current_tab == "add_trade":
            # "Submit Trade" button at (180, 410, 200, 40)
            if 180 <= x <= 380 and 410 <= y <= 450:
                self.submit_add_trade()
            # "Clear Form" button at (400, 410, 120, 40)
            elif 400 <= x <= 520 and 410 <= y <= 450:
                self.init_forms()

        elif self.current_tab == "calculator":
            # "Calculate" button at (240, 350, 180, 40)
            # Calculator updates reactively during draw!
            pass

    def handle_modal_events(self, event: pygame.event.Event):
        """Handle events when a popup modal is open"""
        if self.modal_exit_price_input:
            self.modal_exit_price_input.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            # Close trade confirm button
            if self.active_modal == "close_trade":
                # Confirm button at (520, 480, 140, 36)
                if 520 <= x <= 660 and 480 <= y <= 516:
                    self.submit_close_trade()
                # Cancel button at (675, 480, 100, 36)
                elif 675 <= x <= 775 and 480 <= y <= 516:
                    self.active_modal = None
            elif self.active_modal == "trade_detail":
                # "Close Position" button or "Dismiss" button
                if 700 <= x <= 800 and 520 <= y <= 556:
                    self.active_modal = None
                elif self.modal_trade and self.modal_trade.is_open and 540 <= x <= 680 and 520 <= y <= 556:
                    self.open_close_modal(self.modal_trade)

    def open_close_modal(self, trade: Trade):
        """Open the modal to close an active trade"""
        self.active_modal = "close_trade"
        self.modal_trade = trade
        self.modal_exit_price_input = TextInput(
            pygame.Rect(self.screen_width // 2 - 100, 400, 200, 34),
            placeholder="Exit Price (e.g. 155.00)"
        )
        self.modal_exit_price_input.active = True

    def open_detail_modal(self, trade: Trade):
        """Open trade detail overview modal"""
        self.active_modal = "trade_detail"
        self.modal_trade = trade

    def submit_close_trade(self):
        """Process trade closing from modal"""
        if not self.modal_trade or not self.modal_exit_price_input:
            return
        val_str = self.modal_exit_price_input.text.strip()
        try:
            exit_price = float(val_str)
            closed = self.service.close_trade(self.modal_trade.id, exit_price=exit_price)
            if closed and closed.net_pnl is not None:
                self.trigger_toast(f"Closed {closed.symbol} | Net P&L: ${closed.net_pnl:+.2f}")
            self.active_modal = None
            self.modal_trade = None
        except ValueError:
            self.trigger_toast("Please enter a valid numeric exit price", is_error=True)

    def submit_add_trade(self):
        """Validate and create a new trade from form"""
        try:
            symbol = self.add_inputs["symbol"].text.strip().upper()
            if not symbol:
                self.trigger_toast("Symbol is required", is_error=True)
                return

            t_type = self.add_inputs["trade_type"].text.strip().upper()
            asset_class = self.add_inputs["asset_class"].text.strip().upper() or "STOCKS"
            quantity = float(self.add_inputs["quantity"].text.strip())
            entry_price = float(self.add_inputs["entry_price"].text.strip())

            sl_text = self.add_inputs["stop_loss"].text.strip()
            stop_loss = float(sl_text) if sl_text else None

            tp_text = self.add_inputs["take_profit"].text.strip()
            take_profit = float(tp_text) if tp_text else None

            comm_text = self.add_inputs["commission"].text.strip()
            commission = float(comm_text) if comm_text else 0.0

            setup = self.add_inputs["setup"].text.strip() or "Discretionary"
            notes = self.add_inputs["notes"].text.strip()

            trade = self.service.create_trade(
                symbol=symbol,
                trade_type=t_type,
                asset_class=asset_class,
                quantity=quantity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                commission=commission,
                setup=setup,
                notes=notes,
                status=TradeStatus.OPEN
            )

            self.trigger_toast(f"Trade {trade.id} created successfully!")
            self.current_tab = "trades"
            self.init_forms()

        except ValueError as e:
            self.trigger_toast(f"Input error: {e}", is_error=True)

    def get_filtered_trades(self) -> List[Trade]:
        """Return trades matching active filter and search term"""
        status_filter = None
        if self.trades_filter == "OPEN":
            status_filter = TradeStatus.OPEN
        elif self.trades_filter == "CLOSED":
            status_filter = TradeStatus.CLOSED

        trades = self.service.get_all_trades(status=status_filter)
        query = self.search_input.text.strip().upper()
        if query:
            trades = [t for t in trades if query in t.symbol.upper() or query in t.id.upper() or query in t.setup.upper()]
        return trades

    def draw(self):
        """Master draw call"""
        self.screen.fill(self.colors["BG"])

        # Top Navigation Bar
        self.draw_navbar()

        # Active Tab View
        if self.current_tab == "dashboard":
            self.draw_dashboard()
        elif self.current_tab == "trades":
            self.draw_trades()
        elif self.current_tab == "add_trade":
            self.draw_add_trade()
        elif self.current_tab == "analytics":
            self.draw_analytics()
        elif self.current_tab == "calculator":
            self.draw_calculator()

        # Active Modal Overlay
        if self.active_modal:
            self.draw_modal()

        # Toast notification
        if self.toast_timer > 0:
            self.draw_toast()

    def draw_navbar(self):
        """Render modern top navigation bar"""
        # Header background
        pygame.draw.rect(self.screen, self.colors["HEADER_BG"], (0, 0, self.screen_width, 56))
        pygame.draw.line(self.screen, self.colors["BORDER"], (0, 56), (self.screen_width, 56), 1)

        # App Brand
        logo_text = self.font_title.render("TRADING JOURNAL", True, self.colors["TEXT_MAIN"])
        self.screen.blit(logo_text, (24, 14))
        badge_surf = self.font_small.render("PRO", True, self.colors["BG"])
        badge_rect = pygame.Rect(logo_text.get_width() + 32, 18, 36, 18)
        pygame.draw.rect(self.screen, self.colors["GOLD"], badge_rect, border_radius=3)
        self.screen.blit(badge_surf, (badge_rect.x + 6, badge_rect.y + 2))

        # Nav Tabs
        tabs = [
            ("dashboard", "Dashboard", 220, 90),
            ("trades", "Trades", 320, 80),
            ("add_trade", "+ New Trade", 410, 100),
            ("analytics", "Analytics", 520, 90),
            ("calculator", "Risk Calc", 620, 90)
        ]

        for tab_id, label, tx, tw in tabs:
            is_active = (self.current_tab == tab_id)
            btn_rect = pygame.Rect(tx, 10, tw, 36)

            if is_active:
                pygame.draw.rect(self.screen, self.colors["CARD_BG"], btn_rect, border_radius=4)
                pygame.draw.line(self.screen, self.colors["BLUE"], (tx + 10, 48), (tx + tw - 10, 48), 3)
                col = self.colors["TEXT_MAIN"]
            else:
                col = self.colors["TEXT_MUTED"]

            txt = self.font_body.render(label, True, col)
            self.screen.blit(txt, (tx + (tw - txt.get_width()) // 2, 18))

        # Action Buttons (Export CSV, Samples)
        export_btn = pygame.Rect(990, 12, 105, 32)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], export_btn, border_radius=4)
        pygame.draw.rect(self.screen, self.colors["BORDER"], export_btn, width=1, border_radius=4)
        exp_txt = self.font_small.render("Export CSV", True, self.colors["TEXT_MAIN"])
        self.screen.blit(exp_txt, (export_btn.x + (export_btn.width - exp_txt.get_width()) // 2, export_btn.y + 8))

        sample_btn = pygame.Rect(1105, 12, 110, 32)
        pygame.draw.rect(self.screen, self.colors["BLUE"], sample_btn, border_radius=4)
        smp_txt = self.font_small.render("+ Seed Samples", True, self.colors["TEXT_MAIN"])
        self.screen.blit(smp_txt, (sample_btn.x + (sample_btn.width - smp_txt.get_width()) // 2, sample_btn.y + 8))

    def draw_kpi_card(self, rect: pygame.Rect, title: str, value: str, subtext: str, color: Tuple[int, int, int]):
        """Render a modular KPI metric card"""
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], rect, width=1, border_radius=6)

        t_surf = self.font_small.render(title.upper(), True, self.colors["TEXT_MUTED"])
        self.screen.blit(t_surf, (rect.x + 16, rect.y + 12))

        val_surf = self.font_kpi_value.render(value, True, color)
        self.screen.blit(val_surf, (rect.x + 16, rect.y + 32))

        sub_surf = self.font_small.render(subtext, True, self.colors["TEXT_MUTED"])
        self.screen.blit(sub_surf, (rect.x + 16, rect.y + 68))

    def draw_dashboard(self):
        """Render the primary Executive Dashboard with KPI cards and Equity Curve"""
        perf = self.service.get_performance_summary()
        open_trades = self.service.get_open_trades()

        # 1. KPI Cards Row
        card_w = 186
        card_h = 95
        card_y = 75
        gap = 14

        pnl_val = perf["total_pnl"]
        pnl_col = self.colors["GREEN"] if pnl_val >= 0 else self.colors["RED"]
        pnl_str = f"${pnl_val:+,.2f}"

        kpis = [
            ("Net Realized P&L", pnl_str, f"Gross: ${perf['gross_profit'] - perf['gross_loss']:+,.2f}", pnl_col),
            ("Win Rate", f"{perf['win_rate']:.1f}%", f"{perf['winning_trades']}W / {perf['losing_trades']}L", self.colors["TEXT_MAIN"]),
            ("Profit Factor", str(perf["profit_factor"]), f"Win/Loss: {perf['win_loss_ratio']}", self.colors["GOLD"]),
            ("Expectancy", f"${perf['expectancy']:+,.2f}", f"Avg R: {perf['avg_r_multiple']:+.2f}R", self.colors["BLUE"]),
            ("Max Drawdown", f"${perf['max_drawdown']:,.2f}", f"{perf['max_drawdown_pct']:.1f}% decline", self.colors["RED"]),
            ("Open Positions", str(len(open_trades)), f"{len(perf.get('equity_curve', []))} closed trades", self.colors["TEXT_MAIN"])
        ]

        for i, (title, val, sub, col) in enumerate(kpis):
            x = 24 + i * (card_w + gap)
            self.draw_kpi_card(pygame.Rect(x, card_y, card_w, card_h), title, val, sub, col)

        # 2. Equity Curve Chart Panel
        chart_rect = pygame.Rect(24, 185, 760, 310)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], chart_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], chart_rect, width=1, border_radius=6)

        c_title = self.font_header.render("PORTFOLIO EQUITY CURVE", True, self.colors["TEXT_MAIN"])
        self.screen.blit(c_title, (chart_rect.x + 18, chart_rect.y + 14))
        self.draw_equity_chart(pygame.Rect(chart_rect.x + 20, chart_rect.y + 45, chart_rect.width - 40, chart_rect.height - 65), perf.get("equity_curve", []))

        # 3. Strategy & Directional Breakdown Panel
        stat_rect = pygame.Rect(800, 185, 415, 310)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], stat_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], stat_rect, width=1, border_radius=6)

        s_title = self.font_header.render("RISK & ATTRIBUTION RATIOS", True, self.colors["TEXT_MAIN"])
        self.screen.blit(s_title, (stat_rect.x + 18, stat_rect.y + 14))

        stats = [
            ("Sharpe Ratio", str(perf["sharpe_ratio"])),
            ("Sortino Ratio", str(perf["sortino_ratio"])),
            ("Average Win", f"${perf['average_win']:,.2f}"),
            ("Average Loss", f"${perf['average_loss']:,.2f}"),
            ("Best Trade", f"${perf['best_trade']:+,.2f}"),
            ("Worst Trade", f"${perf['worst_trade']:+,.2f}"),
            ("Max Win Streak", f"{perf['max_win_streak']} trades"),
            ("Max Loss Streak", f"{perf['max_loss_streak']} trades"),
            ("Long Trades P&L", f"${perf['long_pnl']:+,.2f} ({perf['long_win_rate']:.1f}% win)"),
            ("Short Trades P&L", f"${perf['short_pnl']:+,.2f} ({perf['short_win_rate']:.1f}% win)")
        ]

        sy = stat_rect.y + 48
        for label, val in stats:
            lbl_surf = self.font_small.render(label, True, self.colors["TEXT_MUTED"])
            self.screen.blit(lbl_surf, (stat_rect.x + 18, sy))
            v_col = self.colors["GREEN"] if val.startswith("$+") else (self.colors["RED"] if val.startswith("$-") else self.colors["TEXT_MAIN"])
            v_surf = self.font_bold.render(val, True, v_col)
            self.screen.blit(v_surf, (stat_rect.right - 18 - v_surf.get_width(), sy))
            sy += 25

        # 4. Open Positions / Recent Trades Preview Table
        btm_rect = pygame.Rect(24, 510, 1190, 265)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], btm_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], btm_rect, width=1, border_radius=6)

        t_lbl = self.font_header.render("ACTIVE OPEN POSITIONS", True, self.colors["TEXT_MAIN"])
        self.screen.blit(t_lbl, (btm_rect.x + 18, btm_rect.y + 14))

        if not open_trades:
            no_open = self.font_body.render("No active open positions. Head to '+ New Trade' to log an entry.", True, self.colors["TEXT_MUTED"])
            self.screen.blit(no_open, (btm_rect.x + 18, btm_rect.y + 55))
        else:
            # Header
            headers = ["ID", "Symbol", "Direction", "Asset", "Quantity", "Entry Price", "Stop Loss", "Target", "Planned Risk", "Setup", "Action"]
            col_x = [btm_rect.x + 18, btm_rect.x + 110, btm_rect.x + 200, btm_rect.x + 290, btm_rect.x + 380, btm_rect.x + 480, btm_rect.x + 590, btm_rect.x + 690, btm_rect.x + 790, btm_rect.x + 910, btm_rect.x + 1090]
            
            for h, hx in zip(headers, col_x):
                hs = self.font_small.render(h.upper(), True, self.colors["TEXT_MUTED"])
                self.screen.blit(hs, (hx, btm_rect.y + 44))

            pygame.draw.line(self.screen, self.colors["BORDER"], (btm_rect.x + 15, btm_rect.y + 64), (btm_rect.right - 15, btm_rect.y + 64), 1)

            for i, trade in enumerate(open_trades[:4]):
                row_y = btm_rect.y + 74 + i * 42
                # Highlight row background on hover
                m_pos = pygame.mouse.get_pos()
                if btm_rect.x + 10 <= m_pos[0] <= btm_rect.right - 10 and row_y <= m_pos[1] <= row_y + 36:
                    pygame.draw.rect(self.screen, self.colors["CARD_HOVER"], (btm_rect.x + 10, row_y, btm_rect.width - 20, 36), border_radius=4)

                dir_col = self.colors["GREEN"] if trade.is_long else self.colors["RED"]
                sl_str = f"${trade.stop_loss:.2f}" if trade.stop_loss else "--"
                tp_str = f"${trade.take_profit:.2f}" if trade.take_profit else "--"
                risk_str = f"${trade.planned_total_risk:.2f}" if trade.planned_total_risk else "--"

                fields = [
                    (trade.id, self.colors["TEXT_MAIN"]),
                    (trade.symbol, self.colors["GOLD"]),
                    (trade.trade_type.value, dir_col),
                    (trade.asset_class.value, self.colors["TEXT_MUTED"]),
                    (f"{trade.quantity:.2f}", self.colors["TEXT_MAIN"]),
                    (f"${trade.entry_price:.2f}", self.colors["TEXT_MAIN"]),
                    (sl_str, self.colors["RED"]),
                    (tp_str, self.colors["GREEN"]),
                    (risk_str, self.colors["TEXT_MAIN"]),
                    (trade.setup, self.colors["TEXT_MUTED"])
                ]

                for (val, col), hx in zip(fields, col_x[:-1]):
                    s = self.font_body.render(val, True, col)
                    self.screen.blit(s, (hx, row_y + 8))

                # Close Button
                close_rect = pygame.Rect(col_x[-1], row_y + 5, 70, 26)
                pygame.draw.rect(self.screen, self.colors["BLUE"], close_rect, border_radius=4)
                cls_txt = self.font_small.render("Close", True, self.colors["TEXT_MAIN"])
                self.screen.blit(cls_txt, (close_rect.x + (close_rect.width - cls_txt.get_width()) // 2, close_rect.y + 6))

    def draw_equity_chart(self, rect: pygame.Rect, curve: List[Dict[str, Any]]):
        """Render vector chart representing equity growth over time"""
        if not curve or len(curve) < 2:
            no_data = self.font_body.render("Insufficient trade history to plot equity curve.", True, self.colors["TEXT_MUTED"])
            self.screen.blit(no_data, (rect.x + 20, rect.y + rect.height // 2 - 10))
            return

        values = [point["equity"] for point in curve]
        min_val = min(values)
        max_val = max(values)
        padding = (max_val - min_val) * 0.15 if max_val != min_val else 100
        min_y = min_val - padding
        max_y = max_val + padding

        # Grid lines
        for step in (0.25, 0.5, 0.75, 1.0):
            gy = rect.bottom - int(rect.height * step)
            pygame.draw.line(self.screen, self.colors["BORDER"], (rect.x, gy), (rect.right, gy), 1)
            val_at_grid = min_y + (max_y - min_y) * step
            lbl = self.font_small.render(f"${val_at_grid:,.0f}", True, self.colors["TEXT_FAINT"])
            self.screen.blit(lbl, (rect.right - 65, gy - 14))

        # Calculate coordinates
        points = []
        n = len(values)
        for i, v in enumerate(values):
            px = rect.x + int(i * (rect.width - 60) / (n - 1))
            py = rect.bottom - int((v - min_y) / (max_y - min_y) * rect.height)
            points.append((px, py))

        # Draw shaded polygon under curve
        if len(points) >= 2:
            poly_points = [(points[0][0], rect.bottom)] + points + [(points[-1][0], rect.bottom)]
            chart_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            # Offset poly to local surface coords
            local_poly = [(p[0] - rect.x, p[1] - rect.y) for p in poly_points]
            pygame.draw.polygon(chart_surface, (41, 98, 255, 35), local_poly)
            self.screen.blit(chart_surface, (rect.x, rect.y))

            # Main line
            pygame.draw.lines(self.screen, self.colors["BLUE"], False, points, 3)

            # Highlight starting and current balance points
            for pt in (points[0], points[-1]):
                pygame.draw.circle(self.screen, self.colors["TEXT_MAIN"], pt, 5)
                pygame.draw.circle(self.screen, self.colors["BLUE"], pt, 3)

    def draw_trades(self):
        """Render complete scrollable/paginated trades list with filters and search"""
        # Header controls
        # Filter pills: ALL, OPEN, CLOSED
        filter_pills = [("ALL", 40, 60), ("OPEN", 110, 70), ("CLOSED", 190, 80)]
        for f_name, px, pw in filter_pills:
            is_active = (self.trades_filter == f_name)
            p_rect = pygame.Rect(px, 80, pw, 32)
            bg = self.colors["BLUE"] if is_active else self.colors["CARD_BG"]
            pygame.draw.rect(self.screen, self.colors["BORDER"], p_rect, width=1, border_radius=4)
            pygame.draw.rect(self.screen, bg, p_rect, border_radius=4)
            txt = self.font_small.render(f_name, True, self.colors["TEXT_MAIN"])
            self.screen.blit(txt, (p_rect.x + (p_rect.width - txt.get_width()) // 2, p_rect.y + 8))

        # Search Box
        self.search_input.draw(self.screen, self.font_body, self.colors)

        # Table Container
        table_rect = pygame.Rect(24, 125, 1190, 580)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], table_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], table_rect, width=1, border_radius=6)

        # Table Headers
        headers = ["ID", "Symbol", "Type", "Asset", "Qty", "Entry", "Exit", "Net P&L", "Return %", "R-Mult", "Status", "Setup", "Actions"]
        col_x = [table_rect.x + 16, table_rect.x + 105, table_rect.x + 185, table_rect.x + 250, table_rect.x + 325, table_rect.x + 400, table_rect.x + 485, table_rect.x + 575, table_rect.x + 675, table_rect.x + 765, table_rect.x + 845, table_rect.x + 945, table_rect.x + 1090]

        for h, hx in zip(headers, col_x):
            hs = self.font_small.render(h.upper(), True, self.colors["TEXT_MUTED"])
            self.screen.blit(hs, (hx, table_rect.y + 12))

        pygame.draw.line(self.screen, self.colors["BORDER"], (table_rect.x + 10, table_rect.y + 34), (table_rect.right - 10, table_rect.y + 34), 1)

        trades = self.get_filtered_trades()
        start_idx = self.trades_page * self.trades_per_page
        visible_trades = trades[start_idx:start_idx + self.trades_per_page]

        if not visible_trades:
            empty = self.font_body.render("No trades matching criteria.", True, self.colors["TEXT_MUTED"])
            self.screen.blit(empty, (table_rect.x + 20, table_rect.y + 60))
        else:
            m_pos = pygame.mouse.get_pos()
            for i, trade in enumerate(visible_trades):
                ry = table_rect.y + 44 + i * 44
                row_rect = pygame.Rect(table_rect.x + 8, ry, table_rect.width - 16, 38)

                if row_rect.collidepoint(m_pos):
                    pygame.draw.rect(self.screen, self.colors["CARD_HOVER"], row_rect, border_radius=4)

                exit_str = f"${trade.exit_price:.2f}" if trade.exit_price else "--"
                pnl_str = f"${trade.net_pnl:+,.2f}" if trade.net_pnl is not None else "--"
                ret_str = f"{trade.return_pct:+.1f}%" if trade.return_pct is not None else "--"
                r_str = f"{trade.r_multiple:+.2f}R" if trade.r_multiple is not None else "--"

                pnl_col = self.colors["GREEN"] if trade.net_pnl and trade.net_pnl > 0 else (self.colors["RED"] if trade.net_pnl and trade.net_pnl < 0 else self.colors["TEXT_MUTED"])
                dir_col = self.colors["GREEN"] if trade.is_long else self.colors["RED"]
                stat_col = self.colors["GOLD"] if trade.is_open else self.colors["TEXT_MUTED"]

                cols_data = [
                    (trade.id, self.colors["TEXT_MAIN"]),
                    (trade.symbol, self.colors["GOLD"]),
                    (trade.trade_type.value, dir_col),
                    (trade.asset_class.value, self.colors["TEXT_MUTED"]),
                    (f"{trade.quantity:.2f}", self.colors["TEXT_MAIN"]),
                    (f"${trade.entry_price:.2f}", self.colors["TEXT_MAIN"]),
                    (exit_str, self.colors["TEXT_MAIN"]),
                    (pnl_str, pnl_col),
                    (ret_str, pnl_col),
                    (r_str, self.colors["TEXT_MAIN"]),
                    (trade.status.value, stat_col),
                    (trade.setup, self.colors["TEXT_MUTED"])
                ]

                for (val, col), cx in zip(cols_data, col_x[:-1]):
                    s = self.font_body.render(val, True, col)
                    self.screen.blit(s, (cx, ry + 10))

                # Actions: Close (if open) & Delete
                ax = col_x[-1]
                if trade.is_open:
                    cls_btn = pygame.Rect(ax, ry + 6, 45, 26)
                    pygame.draw.rect(self.screen, self.colors["BLUE"], cls_btn, border_radius=3)
                    t_cls = self.font_small.render("Close", True, self.colors["TEXT_MAIN"])
                    self.screen.blit(t_cls, (cls_btn.x + 8, cls_btn.y + 6))

                del_btn = pygame.Rect(ax + 50, ry + 6, 28, 26)
                pygame.draw.rect(self.screen, self.colors["RED_BG"], del_btn, border_radius=3)
                t_del = self.font_small.render("X", True, self.colors["RED"])
                self.screen.blit(t_del, (del_btn.x + 10, del_btn.y + 6))

        # Pagination controls
        py = self.screen_height - 55
        prev_btn = pygame.Rect(40, py, 80, 32)
        next_btn = pygame.Rect(130, py, 80, 32)

        pygame.draw.rect(self.screen, self.colors["CARD_BG"], prev_btn, border_radius=4)
        pygame.draw.rect(self.screen, self.colors["BORDER"], prev_btn, width=1, border_radius=4)
        t_prev = self.font_small.render("< Prev", True, self.colors["TEXT_MAIN"])
        self.screen.blit(t_prev, (prev_btn.x + 18, prev_btn.y + 8))

        pygame.draw.rect(self.screen, self.colors["CARD_BG"], next_btn, border_radius=4)
        pygame.draw.rect(self.screen, self.colors["BORDER"], next_btn, width=1, border_radius=4)
        t_next = self.font_small.render("Next >", True, self.colors["TEXT_MAIN"])
        self.screen.blit(t_next, (next_btn.x + 18, next_btn.y + 8))

        page_str = f"Page {self.trades_page + 1} of {max(1, (len(trades) - 1) // self.trades_per_page + 1)} ({len(trades)} total)"
        page_txt = self.font_small.render(page_str, True, self.colors["TEXT_MUTED"])
        self.screen.blit(page_txt, (230, py + 8))

    def draw_add_trade(self):
        """Render interactive trade entry form with real-time risk calculations"""
        panel_rect = pygame.Rect(24, 75, 1190, 690)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], panel_rect, width=1, border_radius=6)

        title = self.font_header.render("NEW TRADE LOGGING WIZARD", True, self.colors["TEXT_MAIN"])
        self.screen.blit(title, (panel_rect.x + 24, panel_rect.y + 20))

        labels = [
            ("Symbol", 180, 100),
            ("Trade Type (BUY / SHORT)", 180, 145),
            ("Asset Class (STOCKS/FOREX/CRYPTO)", 180, 190),
            ("Quantity / Size", 180, 235),
            ("Entry Price ($)", 180, 280),
            ("Stop Loss ($)", 560, 100),
            ("Take Profit ($)", 560, 145),
            ("Commission / Fees ($)", 560, 190),
            ("Strategy / Setup Tag", 560, 235),
            ("Trade Review & Notes", 180, 330)
        ]

        for text, lx, ly in labels:
            lbl = self.font_small.render(text.upper(), True, self.colors["TEXT_MUTED"])
            self.screen.blit(lbl, (lx, ly))

        # Render Form Inputs
        for inp in self.add_inputs.values():
            inp.draw(self.screen, self.font_body, self.colors)

        # Submit & Clear Buttons
        sub_rect = pygame.Rect(180, 410, 200, 40)
        pygame.draw.rect(self.screen, self.colors["BLUE"], sub_rect, border_radius=4)
        sub_txt = self.font_bold.render("+ Save Trade", True, self.colors["TEXT_MAIN"])
        self.screen.blit(sub_txt, (sub_rect.x + (sub_rect.width - sub_txt.get_width()) // 2, sub_rect.y + 11))

        clr_rect = pygame.Rect(400, 410, 120, 40)
        pygame.draw.rect(self.screen, self.colors["INPUT_BG"], clr_rect, border_radius=4)
        pygame.draw.rect(self.screen, self.colors["BORDER"], clr_rect, width=1, border_radius=4)
        clr_txt = self.font_body.render("Clear", True, self.colors["TEXT_MUTED"])
        self.screen.blit(clr_txt, (clr_rect.x + (clr_rect.width - clr_txt.get_width()) // 2, clr_rect.y + 11))

        # Live Real-time Risk Preview Box on the Right side
        preview_rect = pygame.Rect(800, 120, 380, 330)
        pygame.draw.rect(self.screen, self.colors["INPUT_BG"], preview_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], preview_rect, width=1, border_radius=6)

        prev_title = self.font_header.render("PLANNED TRADE METRICS", True, self.colors["GOLD"])
        self.screen.blit(prev_title, (preview_rect.x + 20, preview_rect.y + 18))

        # Calculate live preview values
        try:
            qty = float(self.add_inputs["quantity"].text.strip() or 0)
            entry = float(self.add_inputs["entry_price"].text.strip() or 0)
            sl = float(self.add_inputs["stop_loss"].text.strip() or 0) if self.add_inputs["stop_loss"].text.strip() else None
            tp = float(self.add_inputs["take_profit"].text.strip() or 0) if self.add_inputs["take_profit"].text.strip() else None
            is_long = self.add_inputs["trade_type"].text.strip().upper() in ("BUY", "LONG")

            invested = qty * entry
            risk_unit = (entry - sl) if is_long else (sl - entry) if sl else 0.0
            reward_unit = (tp - entry) if is_long else (entry - tp) if tp else 0.0
            rr = (reward_unit / risk_unit) if risk_unit > 0 else 0.0
            total_risk = risk_unit * qty if risk_unit > 0 else 0.0

            lines = [
                ("Total Position Capital", f"${invested:,.2f}"),
                ("Risk Per Unit", f"${max(0.0, risk_unit):.2f}" if sl else "--"),
                ("Total Dollar Risk", f"${max(0.0, total_risk):,.2f}" if sl else "--"),
                ("Target Reward Per Unit", f"${max(0.0, reward_unit):.2f}" if tp else "--"),
                ("Planned Reward-to-Risk", f"{rr:.2f}:1" if rr > 0 else "--")
            ]

            ly = preview_rect.y + 55
            for lbl_t, val_t in lines:
                l_s = self.font_body.render(lbl_t, True, self.colors["TEXT_MUTED"])
                self.screen.blit(l_s, (preview_rect.x + 20, ly))
                v_s = self.font_bold.render(val_t, True, self.colors["TEXT_MAIN"])
                self.screen.blit(v_s, (preview_rect.right - 20 - v_s.get_width(), ly))
                ly += 32
        except Exception:
            err_txt = self.font_small.render("Fill valid numbers to preview risk metrics", True, self.colors["TEXT_MUTED"])
            self.screen.blit(err_txt, (preview_rect.x + 20, preview_rect.y + 60))

    def draw_analytics(self):
        """Render in-depth quantitative analytics and performance attribution"""
        perf = self.service.get_performance_summary()
        container = pygame.Rect(24, 75, 1190, 690)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], container, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], container, width=1, border_radius=6)

        title = self.font_header.render("QUANTITATIVE TRADING INTELLIGENCE", True, self.colors["TEXT_MAIN"])
        self.screen.blit(title, (container.x + 24, container.y + 20))

        # Column 1: Performance Summary
        col1_rect = pygame.Rect(container.x + 24, container.y + 60, 360, 600)
        pygame.draw.rect(self.screen, self.colors["INPUT_BG"], col1_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], col1_rect, width=1, border_radius=6)

        c1_title = self.font_header.render("Performance Summary", True, self.colors["GOLD"])
        self.screen.blit(c1_title, (col1_rect.x + 18, col1_rect.y + 16))

        c1_items = [
            ("Total Closed Trades", str(perf["total_trades"])),
            ("Winning Trades", f"{perf['winning_trades']} ({perf['win_rate']:.1f}%)"),
            ("Losing Trades", f"{perf['losing_trades']} ({perf['loss_rate']:.1f}%)"),
            ("Net Profit / Loss", f"${perf['total_pnl']:+,.2f}"),
            ("Gross Profit", f"${perf['gross_profit']:+,.2f}"),
            ("Gross Loss", f"-${perf['gross_loss']:,.2f}"),
            ("Total Commissions Paid", f"${perf['total_commissions']:,.2f}"),
            ("Profit Factor", str(perf["profit_factor"])),
            ("Average Win", f"${perf['average_win']:,.2f}"),
            ("Average Loss", f"${perf['average_loss']:,.2f}"),
            ("Win / Loss Ratio", str(perf["win_loss_ratio"])),
            ("Expectancy ($)", f"${perf['expectancy']:+,.2f}"),
            ("Average R-Multiple", f"{perf['avg_r_multiple']:+.2f}R")
        ]

        cy = col1_rect.y + 55
        for l, v in c1_items:
            ls = self.font_small.render(l, True, self.colors["TEXT_MUTED"])
            self.screen.blit(ls, (col1_rect.x + 18, cy))
            col = self.colors["GREEN"] if v.startswith("$+") else (self.colors["RED"] if v.startswith("$-") or v.startswith("-$") else self.colors["TEXT_MAIN"])
            vs = self.font_bold.render(v, True, col)
            self.screen.blit(vs, (col1_rect.right - 18 - vs.get_width(), cy))
            cy += 38

        # Column 2: Risk & Drawdown
        col2_rect = pygame.Rect(container.x + 410, container.y + 60, 360, 600)
        pygame.draw.rect(self.screen, self.colors["INPUT_BG"], col2_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], col2_rect, width=1, border_radius=6)

        c2_title = self.font_header.render("Risk & Volatility Ratios", True, self.colors["GOLD"])
        self.screen.blit(c2_title, (col2_rect.x + 18, col2_rect.y + 16))

        c2_items = [
            ("Sharpe Ratio", str(perf["sharpe_ratio"])),
            ("Sortino Ratio", str(perf["sortino_ratio"])),
            ("Calmar Ratio", str(perf["calmar_ratio"])),
            ("Max Drawdown ($)", f"${perf['max_drawdown']:,.2f}"),
            ("Max Drawdown (%)", f"{perf['max_drawdown_pct']:.1f}%"),
            ("Recovery Factor", str(perf["recovery_factor"])),
            ("Best Single Trade", f"${perf['best_trade']:+,.2f}"),
            ("Worst Single Trade", f"${perf['worst_trade']:+,.2f}"),
            ("P&L Standard Dev", f"${perf['pnl_std_dev']:,.2f}"),
            ("Max Winning Streak", f"{perf['max_win_streak']} trades"),
            ("Max Losing Streak", f"{perf['max_loss_streak']} trades"),
            ("Current Streak", f"{perf['current_streak']:+d} trades")
        ]

        cy2 = col2_rect.y + 55
        for l, v in c2_items:
            ls = self.font_small.render(l, True, self.colors["TEXT_MUTED"])
            self.screen.blit(ls, (col2_rect.x + 18, cy2))
            vs = self.font_bold.render(v, True, self.colors["TEXT_MAIN"])
            self.screen.blit(vs, (col2_rect.right - 18 - vs.get_width(), cy2))
            cy2 += 38

        # Column 3: Setup & Directional Analysis
        col3_rect = pygame.Rect(container.x + 795, container.y + 60, 365, 600)
        pygame.draw.rect(self.screen, self.colors["INPUT_BG"], col3_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], col3_rect, width=1, border_radius=6)

        c3_title = self.font_header.render("Directional & Strategy Breakdown", True, self.colors["GOLD"])
        self.screen.blit(c3_title, (col3_rect.x + 18, col3_rect.y + 16))

        c3_items = [
            ("Long Positions", f"{perf['long_trades_count']} trades"),
            ("Long Total P&L", f"${perf['long_pnl']:+,.2f}"),
            ("Long Win Rate", f"{perf['long_win_rate']:.1f}%"),
            ("Short Positions", f"{perf['short_trades_count']} trades"),
            ("Short Total P&L", f"${perf['short_pnl']:+,.2f}"),
            ("Short Win Rate", f"{perf['short_win_rate']:.1f}%")
        ]

        cy3 = col3_rect.y + 55
        for l, v in c3_items:
            ls = self.font_small.render(l, True, self.colors["TEXT_MUTED"])
            self.screen.blit(ls, (col3_rect.x + 18, cy3))
            col = self.colors["GREEN"] if v.startswith("$+") else (self.colors["RED"] if v.startswith("$-") else self.colors["TEXT_MAIN"])
            vs = self.font_bold.render(v, True, col)
            self.screen.blit(vs, (col3_rect.right - 18 - vs.get_width(), cy3))
            cy3 += 38

    def draw_calculator(self):
        """Render interactive Position Sizing and Risk Management Calculator"""
        panel_rect = pygame.Rect(24, 75, 1190, 690)
        pygame.draw.rect(self.screen, self.colors["CARD_BG"], panel_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], panel_rect, width=1, border_radius=6)

        title = self.font_header.render("POSITION SIZING & RISK MANAGEMENT CALCULATOR", True, self.colors["TEXT_MAIN"])
        self.screen.blit(title, (panel_rect.x + 24, panel_rect.y + 20))

        labels = [
            ("Account Balance / Equity ($)", 240, 120),
            ("Risk Tolerance (% of Account)", 240, 170),
            ("Entry Price ($)", 240, 220),
            ("Stop Loss Price ($)", 240, 270)
        ]

        for text, lx, ly in labels:
            lbl = self.font_small.render(text.upper(), True, self.colors["TEXT_MUTED"])
            self.screen.blit(lbl, (lx, ly))

        for inp in self.calc_inputs.values():
            inp.draw(self.screen, self.font_body, self.colors)

        # Output Box
        out_rect = pygame.Rect(540, 120, 500, 360)
        pygame.draw.rect(self.screen, self.colors["INPUT_BG"], out_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.colors["BORDER"], out_rect, width=1, border_radius=6)

        out_title = self.font_header.render("CALCULATED ORDER SPECIFICATIONS", True, self.colors["GOLD"])
        self.screen.blit(out_title, (out_rect.x + 24, out_rect.y + 20))

        try:
            acc = float(self.calc_inputs["account_size"].text.strip() or 0)
            risk_pct = float(self.calc_inputs["risk_pct"].text.strip() or 0)
            entry = float(self.calc_inputs["entry_price"].text.strip() or 0)
            sl = float(self.calc_inputs["stop_loss"].text.strip() or 0)

            res = TradingCalculator.calculate_position_size(acc, risk_pct, entry, sl)

            results = [
                ("Max Dollar Risk (R)", f"${res['dollar_risk']:,.2f}", self.colors["RED"]),
                ("Risk Per Unit", f"${res['risk_per_unit']:,.2f}", self.colors["TEXT_MAIN"]),
                ("Recommended Position Units", f"{res['shares']:,.2f}", self.colors["GREEN"]),
                ("Total Position Value", f"${res['position_value']:,.2f}", self.colors["TEXT_MAIN"]),
                ("Account Leverage", f"{res['leverage']:.2f}x", self.colors["GOLD"] if res['leverage'] > 1.0 else self.colors["TEXT_MAIN"])
            ]

            ry = out_rect.y + 65
            for label, val, col in results:
                lbl_surf = self.font_body.render(label, True, self.colors["TEXT_MUTED"])
                self.screen.blit(lbl_surf, (out_rect.x + 24, ry))
                v_surf = self.font_bold.render(val, True, col)
                self.screen.blit(v_surf, (out_rect.right - 24 - v_surf.get_width(), ry))
                ry += 42

        except Exception as ex:
            err = self.font_body.render("Enter valid positive numbers in all fields.", True, self.colors["TEXT_MUTED"])
            self.screen.blit(err, (out_rect.x + 24, out_rect.y + 70))

    def draw_modal(self):
        """Render active popup modal dialog"""
        # Dim overlay
        dim_surf = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        dim_surf.fill((0, 0, 0, 160))
        self.screen.blit(dim_surf, (0, 0))

        modal_w, modal_h = 560, 380
        mx = (self.screen_width - modal_w) // 2
        my = (self.screen_height - modal_h) // 2
        m_rect = pygame.Rect(mx, my, modal_w, modal_h)

        pygame.draw.rect(self.screen, self.colors["CARD_BG"], m_rect, border_radius=8)
        pygame.draw.rect(self.screen, self.colors["BORDER_LIGHT"], m_rect, width=1, border_radius=8)

        if self.active_modal == "close_trade" and self.modal_trade:
            title = self.font_header.render(f"CLOSE TRADE: {self.modal_trade.symbol} ({self.modal_trade.id})", True, self.colors["TEXT_MAIN"])
            self.screen.blit(title, (mx + 24, my + 24))

            dir_str = self.modal_trade.trade_type.value
            entry_str = f"${self.modal_trade.entry_price:.2f}"
            qty_str = f"{self.modal_trade.quantity:.2f}"
            info_str = f"Position: {dir_str} {qty_str} units @ {entry_str}"
            info_txt = self.font_body.render(info_str, True, self.colors["TEXT_MUTED"])
            self.screen.blit(info_txt, (mx + 24, my + 60))

            lbl = self.font_small.render("EXIT / EXECUTION PRICE ($)", True, self.colors["TEXT_MUTED"])
            self.screen.blit(lbl, (self.modal_exit_price_input.rect.x, self.modal_exit_price_input.rect.y - 20))
            self.modal_exit_price_input.draw(self.screen, self.font_body, self.colors)

            # Confirm Button
            cnf_btn = pygame.Rect(mx + 80, my + 300, 180, 40)
            pygame.draw.rect(self.screen, self.colors["GREEN"], cnf_btn, border_radius=4)
            c_txt = self.font_bold.render("Confirm Close", True, self.colors["BG"])
            self.screen.blit(c_txt, (cnf_btn.x + (cnf_btn.width - c_txt.get_width()) // 2, cnf_btn.y + 11))

            # Cancel Button
            can_btn = pygame.Rect(mx + 290, my + 300, 120, 40)
            pygame.draw.rect(self.screen, self.colors["INPUT_BG"], can_btn, border_radius=4)
            pygame.draw.rect(self.screen, self.colors["BORDER"], can_btn, width=1, border_radius=4)
            cn_txt = self.font_body.render("Cancel", True, self.colors["TEXT_MAIN"])
            self.screen.blit(cn_txt, (can_btn.x + (can_btn.width - cn_txt.get_width()) // 2, can_btn.y + 11))

        elif self.active_modal == "trade_detail" and self.modal_trade:
            t = self.modal_trade
            title = self.font_header.render(f"TRADE DETAILS: {t.symbol} ({t.id})", True, self.colors["GOLD"])
            self.screen.blit(title, (mx + 24, my + 24))

            details = [
                ("Status", t.status.value),
                ("Direction", t.trade_type.value),
                ("Asset Class", t.asset_class.value),
                ("Quantity", f"{t.quantity:.2f}"),
                ("Entry Price", f"${t.entry_price:.2f}"),
                ("Exit Price", f"${t.exit_price:.2f}" if t.exit_price else "--"),
                ("Stop Loss", f"${t.stop_loss:.2f}" if t.stop_loss else "--"),
                ("Take Profit", f"${t.take_profit:.2f}" if t.take_profit else "--"),
                ("Net Realized P&L", f"${t.net_pnl:+,.2f}" if t.net_pnl is not None else "--"),
                ("R-Multiple", f"{t.r_multiple:+.2f}R" if t.r_multiple is not None else "--"),
                ("Strategy Setup", t.setup),
                ("Trade Notes", t.notes if t.notes else "--")
            ]

            dy = my + 60
            for label, val in details:
                ls = self.font_small.render(label, True, self.colors["TEXT_MUTED"])
                self.screen.blit(ls, (mx + 24, dy))
                vs = self.font_body.render(val, True, self.colors["TEXT_MAIN"])
                self.screen.blit(vs, (mx + 170, dy))
                dy += 22

            # Close button
            cls_btn = pygame.Rect(mx + modal_w - 120, my + modal_h - 50, 96, 34)
            pygame.draw.rect(self.screen, self.colors["BLUE"], cls_btn, border_radius=4)
            c_txt = self.font_body.render("Dismiss", True, self.colors["TEXT_MAIN"])
            self.screen.blit(c_txt, (cls_btn.x + 22, cls_btn.y + 8))

    def draw_toast(self):
        """Render floating notification pill"""
        txt = self.font_small.render(self.toast_message, True, self.colors["TEXT_MAIN"])
        toast_w = txt.get_width() + 32
        toast_rect = pygame.Rect((self.screen_width - toast_w) // 2, 70, toast_w, 32)
        pygame.draw.rect(self.screen, self.toast_color, toast_rect, border_radius=16)
        self.screen.blit(txt, (toast_rect.x + 16, toast_rect.y + 8))
