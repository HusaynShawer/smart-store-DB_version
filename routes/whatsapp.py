# routes/whatsapp.py
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from agents.backend_service import BackendService

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])
backend = BackendService()
@router.get("/test")
async def test():
    """اختبار بسيط"""
    return {
        "success": True,
        "message": "WhatsApp router is working!",
        "endpoints": [
            "GET /whatsapp/test",
            "POST /whatsapp/test-auto",
            "POST /whatsapp/setup-callmebot"
        ]
    }

@router.post("/test-auto")
async def test_auto_whatsapp(
    vendor_phone: str = Query(..., description="رقم التاجر"),
    message: Optional[str] = Query(None, description="الرسالة")
):
    """اختبار الإرسال التلقائي للواتساب"""
    try:
        if not message:
            message = "مرحباً، هذا اختبار للإرسال التلقائي من متجر زكي ✅"
        
        result = await backend.send_test_whatsapp(vendor_phone, message)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/setup-callmebot")
async def setup_callmebot(
    api_key: str = Query(..., description="API Key من CallMeBot")
):
    """تثبيت CallMeBot API"""
    try:
        # Save to .env file
        import os
        env_path = ".env"
        
        if os.path.exists(env_path):
            with open(env_path, 'a') as f:
                f.write(f"\nCALLMEBOT_API_KEY={api_key}\n")
        else:
            with open(env_path, 'w') as f:
                f.write(f"CALLMEBOT_API_KEY={api_key}\n")
        
        return {
            "success": True,
            "message": "تم حفظ API Key بنجاح",
            "instructions": "أعد تشغيل السيرفر ليتم تفعيل الإرسال التلقائي"
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))