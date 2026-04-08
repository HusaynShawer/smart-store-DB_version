# test_meta.py
"""
اختبار Meta WhatsApp Service بدل Twilio.
"""
import asyncio
from agents.meta_service import get_meta_service, format_phone_eg


async def test_phone_formatting():
    """اختبار تنسيق الأرقام."""
    test_numbers = [
        "01552424553",
    ]
    print("=" * 55)
    print("🧪 اختبار تنسيق الأرقام")
    print("=" * 55)
    for num in test_numbers:
        formatted = format_phone_eg(num)
        print(f"الأصلي: {num:22} ← المنسق: {formatted}")


async def test_send_message():
    """اختبار إرسال رسالة حقيقية."""
    meta = get_meta_service()

    if not meta.is_available():
        print("❌ Meta غير مضبوط — تحقق من META_ACCESS_TOKEN و META_PHONE_NUMBER_ID في .env")
        return

    YOUR_PHONE = "01234567890"  # ← غير ده برقمك

    result = await meta.send_message(
        to_phone=YOUR_PHONE,
        message="🧪 اختبار من متجر زكي — لو وصلت الرسالة، Meta WhatsApp شغال ✅",
    )

    print("\n" + "=" * 55)
    print("📤 نتيجة الإرسال:")
    print("=" * 55)
    print(f"نجاح     : {result.get('success')}")
    print(f"Message ID: {result.get('message_id')}")
    if result.get("error"):
        print(f"خطأ      : {result.get('error')}")


async def test_vendor_notification():
    """اختبار إشعار التاجر."""
    meta = get_meta_service()
    if not meta.is_available():
        print("❌ Meta غير مضبوط")
        return

    result = await meta.send_vendor_notification(
        vendor_phone="01001111222",   # ← رقم التاجر للاختبار
        customer_name="أحمد محمد",
        customer_phone="01099999999",
        product_name="iPhone 15 Pro",
        product_price=1299.0,
        order_id=999,
        shop_name="موبايلي - قنا",
    )
    print(f"\n📦 إشعار التاجر: {'✅ نجح' if result.get('success') else '❌ فشل'}")


if __name__ == "__main__":
    asyncio.run(test_phone_formatting())

    choice = input("\nاختبار إرسال رسالة حقيقية؟ (y/n): ")
    if choice.lower() == "y":
        asyncio.run(test_send_message())

    choice2 = input("اختبار إشعار تاجر؟ (y/n): ")
    if choice2.lower() == "y":
        asyncio.run(test_vendor_notification())