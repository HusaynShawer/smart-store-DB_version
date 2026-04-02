#!/usr/bin/env python3
"""
seed.py — إضافة البيانات الأساسية للمتاجر مع أرقام واتساب فريدة لكل تاجر
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

DATABASE_URL = (
    "mysql+aiomysql://zaki:zakipass@mysql:3306/zaki_store?charset=utf8mb4"
)

# منتجات أساسية
PRODUCTS = [
    {"title": "iPhone 15 Pro Max", "price": 1299.00, "category": "electronics", "description": "A17 Pro chip, Titanium design", "image": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=200&q=80", "rating_rate": 4.9, "rating_count": 1200},
    {"title": "Samsung Galaxy S24 Ultra", "price": 1199.00, "category": "electronics", "description": "AI powered, S Pen included", "image": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=200&q=80", "rating_rate": 4.8, "rating_count": 850},
    {"title": "MacBook Pro 14 inch", "price": 1999.00, "category": "electronics", "description": "M3 Pro chip", "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=200&q=80", "rating_rate": 4.9, "rating_count": 950},
    {"title": "Mens Cotton Jacket", "price": 55.99, "category": "men's clothing", "description": "Great outerwear jacket", "image": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=200&q=80", "rating_rate": 4.7, "rating_count": 500},
    {"title": "Gold Diamond Ring", "price": 899.00, "category": "jewelery", "description": "18K gold with 1 carat diamond", "image": "https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=200&q=80", "rating_rate": 4.7, "rating_count": 230},
]

# كل متجر له رقم واتساب خاص به
STORES = [
    # متاجر إلكترونيات - كل واحد رقم مختلف
    {"name": "موبايلي - قنا", "governorate": "قنا", "lat": 26.1551, "lon": 32.7160, "phone": "01001111222", "products_csv": "phone,mobile,iphone,samsung,موبايل"},
    {"name": "تك وورلد - الأقصر", "governorate": "الأقصر", "lat": 25.6872, "lon": 32.6396, "phone": "01002222333", "products_csv": "phone,laptop,monitor,موبايل,لابتوب"},
    {"name": "القاهرة للتقنية", "governorate": "القاهرة", "lat": 30.0444, "lon": 31.2357, "phone": "01003333444", "products_csv": "phone,laptop,monitor,gaming,موبايل,لابتوب"},
    {"name": "الإسكندرية تك", "governorate": "الإسكندرية", "lat": 31.2001, "lon": 29.9187, "phone": "01004444555", "products_csv": "phone,laptop,tablet,موبايل,لابتوب"},
    {"name": "زكي للتكنولوجيا", "governorate": "الجيزة", "lat": 30.0131, "lon": 31.2089, "phone": "01552424553", "products_csv": "phone,laptop,iphone,samsung,موبايل,لابتوب"},
    
    # متاجر ملابس - كل واحد رقم مختلف
    {"name": "فاشون هاوس - قنا", "governorate": "قنا", "lat": 26.1600, "lon": 32.7200, "phone": "01005555666", "products_csv": "jacket,shirt,clothing,جاكيت,ملابس,قميص"},
    {"name": "ستايل هاوس - القاهرة", "governorate": "القاهرة", "lat": 30.0444, "lon": 31.2357, "phone": "01006666777", "products_csv": "jacket,shirt,tshirt,clothing,جاكيت,تيشرت"},
    {"name": "مودا ستور - الإسكندرية", "governorate": "الإسكندرية", "lat": 31.2001, "lon": 29.9187, "phone": "01007777888", "products_csv": "jacket,shirt,women clothing,ملابس,موضة"},
    
    # متاجر مجوهرات - كل واحد رقم مختلف
    {"name": "جولدن جول - قنا", "governorate": "قنا", "lat": 26.1580, "lon": 32.7140, "phone": "01008888999", "products_csv": "ring,gold,jewelry,earring,خاتم,ذهب,مجوهرات"},
    {"name": "زكي للمجوهرات", "governorate": "الجيزة", "lat": 30.0131, "lon": 31.2089, "phone": "01552424553", "products_csv": "ring,necklace,earring,gold,silver,خاتم,قلادة,ذهب"},
    {"name": "دياموند هاوس", "governorate": "القاهرة", "lat": 30.0444, "lon": 31.2357, "phone": "01009999000", "products_csv": "ring,diamond,gold,خاتم,ألماس,ذهب"},
    
    # متاجر إضافية
    {"name": "توب تك - أسيوط", "governorate": "أسيوط", "lat": 27.1809, "lon": 31.1837, "phone": "01001111000", "products_csv": "phone,laptop,monitor,موبايل"},
    {"name": "إلكترو سوق", "governorate": "المنيا", "lat": 28.1099, "lon": 30.7503, "phone": "01002222111", "products_csv": "electronics,phone,laptop,الكترونيات"},
]


async def seed():
    from config.database import Base, ProductModel, StoreModel

    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("🗑️  جاري مسح البيانات القديمة...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ تم إنشاء الجداول من جديد")

    async with Session() as db:
        # إضافة المنتجات
        print(f"📦 جاري إضافة {len(PRODUCTS)} منتج...")
        for p in PRODUCTS:
            db.add(ProductModel(**p))
        await db.commit()
        print(f"✅ تمت إضافة {len(PRODUCTS)} منتج")

        # إضافة المتاجر بأرقام واتساب مختلفة
        print(f"🏪 جاري إضافة {len(STORES)} متجر...")
        for s in STORES:
            db.add(StoreModel(**s))
        await db.commit()
        print(f"✅ تمت إضافة {len(STORES)} متجر")

        # عرض ملخص المتاجر وأرقام الواتساب
        print("\n" + "="*60)
        print("📊 ملخص المتاجر وأرقام الواتساب:")
        print("="*60)
        
        for store in STORES:
            print(f"🏪 {store['name']}")
            print(f"   📍 {store['governorate']}")
            print(f"   📞 واتساب: {store['phone']}")
            print(f"   📦 منتجات: {store['products_csv']}")
            print("-"*40)

    await engine.dispose()
    
    print("\n" + "="*60)
    print("🎉 تمت إضافة البيانات بنجاح!")
    print("="*60)
    print("\n💡 ملاحظات مهمة:")
    print("   ✅ كل متجر له رقم واتساب خاص به")
    print("   ✅ عندما يشتري عميل منتج، سيتم إرسال الطلب للتاجر المناسب")
    print("   ✅ العميل سيرى رابط واتساب خاص بالتاجر")


if __name__ == "__main__":
    print("⚠️  تنبيه: هذا السكربت سيمسح كل البيانات الموجودة ويضيف بيانات جديدة!")
    print("⚠️  اضغط Ctrl+C خلال 5 ثواني للإلغاء...")
    import time
    time.sleep(5)
    
    asyncio.run(seed())