
import asyncio
import logging
from collections import defaultdict

import win32con
import win32print
import win32ui

from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, DisconnectEvent, GiftEvent


# ============================================================
# SETTINGS
# ============================================================

TIKTOK_USERNAME = "brat_thewurst"
COIN_THRESHOLD = 30

# False = print actual labels
# True = test without printing
TEST_MODE = False

# Smaller gifts accumulate separately for each viewer.
small_gift_totals = defaultdict(int)


# ============================================================
# LABEL PRINTER
# ==============================================


def print_username(label_text):
    printer_name = win32print.GetDefaultPrinter()
    dc = win32ui.CreateDC()

    try:
        dc.CreatePrinterDC(printer_name)

        width = dc.GetDeviceCaps(win32con.HORZRES)
        height = dc.GetDeviceCaps(win32con.VERTRES)

        dc.StartDoc("TikTok Gift Label")
        dc.StartPage()
        dc.SetBkMode(win32con.TRANSPARENT)

        lines = label_text.split("\n")

        # Keep text away from the edges of the label.
        max_width = int(width * 0.90)
        max_height = int(height * 0.85)

        # Use a larger font when possible, shrink for long names.
        base_font_size = int(height * 0.25)
        min_font_size = max(1, int(height * 0.08))

        for font_size in range(
            base_font_size, min_font_size - 1, -1
        ):
            font = win32ui.CreateFont({
                "name": "Arial",
                "height": -font_size,
                "weight": win32con.FW_BOLD,
            })

            dc.SelectObject(font)

            sizes = [dc.GetTextExtent(line) for line in lines]
            widest_line = max(
                (size[0] for size in sizes), default=0
            )
            total_height = sum(size[1] for size in sizes)

            if (
                widest_line <= max_width
                and total_height <= max_height
            ):
                break

        # Recheck the dimensions of the selected font.
        sizes = [dc.GetTextExtent(line) for line in lines]
        line_widths = [size[0] for size in sizes]
        line_heights = [size[1] for size in sizes]

        total_height = sum(line_heights)
        y = max(0, (height - total_height) // 2)

        for line, line_width, line_height in zip(
            lines, line_widths, line_heights
        ):
            x = max(0, (width - line_width) // 2)
            dc.TextOut(x, y, line)
            y += line_height

        dc.EndPage()
        dc.EndDoc()

        print(f"LABEL SENT TO PRINTER:\n{label_text}")

    except Exception:
        try:
            dc.AbortDoc()
        except Exception:
            pass
        raise

    finally:
        dc.DeleteDC()


# ============================================================
# TIKTOK LIVE CLIENT
# ============================================================

client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)


@client.on(ConnectEvent)
async def on_connect(event: ConnectEvent):
    print("CONNECTED TO TIKTOK LIVE!")
    print(f"Creator: @{TIKTOK_USERNAME}")
    print(f"Room ID: {client.room_id}")
    print("Waiting for gifts...")


@client.on(DisconnectEvent)
async def on_disconnect(event: DisconnectEvent):
    print("TikTok LIVE disconnected.")


# ============================================================
# GIFT HANDLER
# ============================================================

@client.on(GiftEvent)
async def on_gift(event: GiftEvent):
    try:
        if event.user is None or event.gift is None:
            return

        username = event.user.unique_id
        nickname = getattr(event.user, "nickname", "") or ""
        gift = event.gift

        # Ignore intermediate events during a gift streak.
        if getattr(event, "streaking", False):
            return

        coin_cost = getattr(gift, "diamond_count", None)

        if coin_cost is None:
            print(
                f"Gift value unavailable for @{username}; skipping."
            )
            return

        coin_cost = int(coin_cost)
        quantity = max(
            1, int(getattr(event, "repeat_count", 1) or 1)
        )

        gift_name = getattr(gift, "name", "Unknown gift")

        print(
            f"GIFT: @{username} ({nickname}) | {gift_name} | "
            f"{coin_cost} coins each | quantity: {quantity}"
        )

        labels_to_print = 0

        if coin_cost >= COIN_THRESHOLD:
            # Each qualifying gift gets its own label.
            labels_to_print = quantity
        else:
            # Accumulate the value of smaller gifts.
            small_gift_totals[username] += coin_cost * quantity

            labels_to_print = (
                small_gift_totals[username] // COIN_THRESHOLD
            )

            small_gift_totals[username] %= COIN_THRESHOLD

            print(
                f"@{username} small-gift balance: "
                f"{small_gift_totals[username]}/"
                f"{COIN_THRESHOLD} coins"
            )

        for _ in range(labels_to_print):
            label_text = f"@{username}\n{nickname}"

            if TEST_MODE:
                print(f"[TEST MODE] Would print:\n{label_text}")
            else:
                await asyncio.to_thread(
                    print_username, label_text
                )

    except Exception as exc:
        print(f"GIFT HANDLER ERROR: {exc}")


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    print("=" * 45)
    print("TIKTOK LIVE LABEL PRINTER")
    print("=" * 45)
    print(f"Creator: @{TIKTOK_USERNAME}")
    print(f"Coin threshold: {COIN_THRESHOLD}")
    print(f"Test mode: {TEST_MODE}")
    print("Connecting to TikTok LIVE...")

    try:
        client.run(fetch_gift_info=True)

    except KeyboardInterrupt:
        print("\nPrinter stopped by user.")

    except Exception as exc:
        print(f"\nCONNECTION ERROR: {exc}")
        print(
            "Check that the creator is LIVE and try again."
        )
