# agents/twilio_service.py

"""
TwilioService — Sends WhatsApp messages to vendors via Twilio API.
"""
import logging
import re
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class TwilioService:
    """Service to send WhatsApp messages to vendors using Twilio."""
    
    def __init__(self):
        self.client = None
        self._initialized = False
        self._init_client()
    
    def _init_client(self):
        """Initialize Twilio client if credentials are available."""
        if (settings.TWILIO_ACCOUNT_SID and 
            settings.TWILIO_AUTH_TOKEN and 
            settings.TWILIO_WHATSAPP_NUMBER):
            try:
                self.client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
                self._initialized = True
                logger.info(" Twilio client initialized successfully")
                logger.info(f"   WhatsApp from number: {settings.TWILIO_WHATSAPP_NUMBER}")
            except Exception as exc:
                logger.error(f" Failed to initialize Twilio client: {exc}")
                self._initialized = False
        else:
            logger.warning(" Twilio credentials not configured. Messages will not be sent.")
            logger.warning(f" TWILIO_ACCOUNT_SID: {'' if settings.TWILIO_ACCOUNT_SID else '✗'}")
            logger.warning(f" TWILIO_AUTH_TOKEN: {'' if settings.TWILIO_AUTH_TOKEN else '✗'}")
            logger.warning(f" TWILIO_WHATSAPP_NUMBER: {'' if settings.TWILIO_WHATSAPP_NUMBER else '✗'}")
            self._initialized = False
    
    def is_available(self) -> bool:
        """Check if Twilio service is available."""
        return self._initialized and self.client is not None
    
    def format_phone_number(self, phone: str) -> str:
        """
        Format Egyptian phone number for Twilio WhatsApp.
        
        Input formats supported:
        - 01001111222  → +201001111222
        - 010 0111 1222 → +201001111222
        - +201001111222 → +201001111222
        - 201001111222  → +201001111222
        
        Returns:
            str: Formatted phone number with +20 prefix
        """
        if not phone:
            return ""
        
        # Remove all non-digit characters
        cleaned = re.sub(r'\D', '', phone)
        
        logger.debug(f"Original phone: {phone} → Cleaned: {cleaned}")
        
        # Egyptian numbers start with 010, 011, 012, 015
        if cleaned.startswith('0') and len(cleaned) == 11:
            # 01001111222 → 201001111222
            cleaned = '20' + cleaned[1:]
            logger.debug(f"Converted Egyptian mobile: +{cleaned}")
        elif cleaned.startswith('20') and len(cleaned) == 12:
            # 201001111222 → keep as is
            pass
        elif not cleaned.startswith('20') and len(cleaned) == 10:
            # 1001111222 → add 20
            cleaned = '20' + cleaned
            logger.debug(f"Added country code: +{cleaned}")
        elif len(cleaned) == 12 and cleaned.startswith('2'):
            # 201001111222 (without +) → add +
            pass
        else:
            logger.warning(f"Unrecognized phone format: {phone} → cleaned: {cleaned}")
            # Default: assume it's Egyptian and add 20
            if len(cleaned) == 10:
                cleaned = '20' + cleaned
            elif len(cleaned) == 11 and cleaned.startswith('0'):
                cleaned = '20' + cleaned[1:]
        
        # Add + prefix
        formatted = f"+{cleaned}"
        logger.info(f"📱 Formatted phone: {phone} → {formatted}")
        
        return formatted
    
    def send_whatsapp_message(
        self,
        to_phone: str,
        message: str,
        from_phone: Optional[str] = None
    ) -> dict:
        """
        Send WhatsApp message to a vendor.
        
        Args:
            to_phone: Vendor's phone number (e.g., "01001111222")
            message: Message content to send
            from_phone: Optional custom from number (uses settings if not provided)
        
        Returns:
            dict: Result with success status and message SID if successful
        """
        if not self.is_available():
            logger.warning(" Twilio not available. Cannot send message.")
            print("=" * 50)
            print(" Twilio not available. Cannot send message.")
            print("=" * 50)
            return {
                "success": False,
                "error": "Twilio service not configured",
                "message": "يرجى تكوين خدمة Twilio أولاً"
            }
        
        if not to_phone:
            logger.warning(" No recipient phone number provided")
            print("=" * 50)
            print("No recipient phone number provided")
            print("=" * 50)
            return {
                "success": False,
                "error": "No recipient phone number",
                "message": "رقم المستلم غير موجود"
            }
        
        try:
            # Format phone numbers
            formatted_to = self.format_phone_number(to_phone)
            formatted_from = from_phone or settings.TWILIO_WHATSAPP_NUMBER
            
            # Add whatsapp: prefix for Twilio
            if not formatted_to.startswith('whatsapp:'):
                formatted_to = f"whatsapp:{formatted_to}"
            
            if not formatted_from.startswith('whatsapp:'):
                formatted_from = f"whatsapp:{formatted_from}"
            
            logger.info(f"📤 Sending WhatsApp message:")
            logger.info(f"   From: {formatted_from}")
            logger.info(f"   To: {formatted_to}")
            logger.info(f"   Message: {message[:100]}...")
            
            # Send message
            twilio_message = self.client.messages.create(
                body=message,
                from_=formatted_from,
                to=formatted_to
            )
            
            logger.info(f" WhatsApp message sent successfully!")
            logger.info(f" SID: {twilio_message.sid}")
            logger.info(f" Status: {twilio_message.status}")

            print("=" * 50)
            print(f"Message sent successfully!")
            print(f"To number : {to_phone}")
            print(f"Formatted : {formatted_to}")
            print(f"SID       : {twilio_message.sid}")
            print(f"Status    : {twilio_message.status}")
            print("=" * 50)
            
            return {
                "success": True,
                "message_sid": twilio_message.sid,
                "status": twilio_message.status,
                "to": to_phone,
                "formatted_to": formatted_to
            }
            
        except TwilioRestException as exc:
            print("=" * 50)
            print(f"Failed to send message!")
            print(f"To number : {to_phone}")
            print(f"Error     : {exc.msg}")
            print(f"Code      : {exc.code}")
            print("=" * 50)

            logger.error(f" Twilio error sending to {to_phone}:")
            logger.error(f" Code: {exc.code}")
            logger.error(f" Message: {exc.msg}")
            return {
                "success": False,
                "error": exc.msg,
                "code": exc.code,
                "to": to_phone
            }
        except Exception as exc:
            print("=" * 50)
            print(f"Unexpected error sending WhatsApp!")
            print(f"To number : {to_phone}")
            print(f"Error     : {exc}")
            print("=" * 50)

            logger.error(f" Unexpected error sending WhatsApp: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "to": to_phone
            }
    
    def send_vendor_notification(
        self,
        vendor_phone: str,
        customer_name: str,
        customer_phone: str,
        product_name: str,
        product_price: float,
        order_id: int
    ) -> dict:
        """
        Send formatted order notification to vendor.
        
        Args:
            vendor_phone: Vendor's phone number (e.g., "01001111222")
            customer_name: Customer's name
            customer_phone: Customer's phone number
            product_name: Product name
            product_price: Product price
            order_id: Order ID for reference
        
        Returns:
            dict: Result of sending operation
        """
        message = (
            f"طلب جديد من متجر زكي\n"
            f"───────────────────\n"
            f"المنتج: {product_name}\n"
            f"السعر: ${product_price}\n"
            f"العميل: {customer_name}\n"
            f"رقم العميل: {customer_phone}\n"
            f"رقم الطلب: #{order_id}\n"
            f"───────────────────\n"
            f"يرجى التواصل مع العميل لتأكيد الطلب "
        )
        
        logger.info(f" Sending vendor notification to {vendor_phone} for order #{order_id}")
        print(f"\n Sending vendor notification → {vendor_phone} | Order #{order_id}")
        return self.send_whatsapp_message(vendor_phone, message)
    
    def send_customer_confirmation(
        self,
        customer_phone: str,
        product_name: str,
        vendor_name: str,
        vendor_phone: str
    ) -> dict:
        """
        Send confirmation to customer that order was sent to vendor.
        
        Args:
            customer_phone: Customer's phone number
            product_name: Product name
            vendor_name: Vendor/Store name
            vendor_phone: Vendor's phone number for reference
        
        Returns:
            dict: Result of sending operation
        """
        # Format vendor phone for display
        vendor_display = vendor_phone
        if vendor_phone.startswith('+20'):
            vendor_display = '0' + vendor_phone[3:]
        
        message = (
            f" تم إرسال طلبك بنجاح!\n"
            f"───────────────────\n"
            f" المنتج: {product_name}\n"
            f"المتجر: {vendor_name}\n"
            f" هيتواصل معاك التاجر على: {vendor_display}\n"
            f"───────────────────\n"
            f"شكراً لتسوقك مع متجر زكي "
        )
        
        logger.info(f" Sending customer confirmation to {customer_phone}")
        print(f"\n Sending customer confirmation → {customer_phone}")
        return self.send_whatsapp_message(customer_phone, message)


# Singleton instance
_twilio_service = None


def get_twilio_service() -> TwilioService:
    """Get or create Twilio service instance."""
    global _twilio_service
    if _twilio_service is None:
        _twilio_service = TwilioService()
    return _twilio_service