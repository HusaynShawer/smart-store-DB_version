# test_twilio.py
import asyncio
from agents.twilio_service import get_twilio_service

async def test_phone_formatting():
    """Test phone number formatting"""
    twilio = get_twilio_service()
    
    test_numbers = [
        "01001111222",      # رقم من seed.py
        "01002222333",
        "01552424553",
        "01234567890",
        "+201001111222",
        "201001111222",
        "1001111222",
    ]
    
    print("="*60)
    print("🧪 اختبار صيغة الأرقام")
    print("="*60)
    
    for num in test_numbers:
        formatted = twilio.format_phone_number(num)
        print(f"Original: {num:20} → Formatted: {formatted}")
    
    print("\n" + "="*60)

async def test_send_message():
    """Test sending actual message (use your own number)"""
    twilio = get_twilio_service()
    
    if not twilio.is_available():
        print("❌ Twilio not available. Check your .env configuration")
        return
    
    # استخدم رقمك الشخصي للاختبار
    YOUR_PHONE = "01234567890"  # غير ده برقمك
    
    result = twilio.send_whatsapp_message(
        to_phone=YOUR_PHONE,
        message="🧪 اختبار من متجر زكي - لو وصلت الرسالة، Twilio شغال ✅"
    )
    
    print("\n" + "="*60)
    print("📤 نتيجة الإرسال:")
    print("="*60)
    print(f"Success: {result.get('success')}")
    print(f"Message: {result.get('message')}")
    print(f"SID: {result.get('message_sid')}")
    print(f"Status: {result.get('status')}")
    if result.get('error'):
        print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_phone_formatting())
    print("\n")
    
    # اختياري: جرب تبعت رسالة
    choice = input("هل تريد اختبار إرسال رسالة فعلية؟ (y/n): ")
    if choice.lower() == 'y':
        asyncio.run(test_send_message())