# app/seed.py
"""Seed the database with products, stores, and their pgvector embeddings.

Run from the backend directory:
    python -m app.seed

⚠️  This wipes `products` and `stores` tables and re-creates them.
"""
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.embeddings import get_embedding_service
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.models import ProductModel, StoreModel
from app.services.product_service import product_embedding_text

settings = get_settings()
setup_logging("INFO")

PRODUCTS = [
    # ── Electronics: smartphones & tablets ──────────────────────────────
    {"title": "iPhone 15 Pro Max", "price": 1299.00, "category": "electronics",
     "description": "A17 Pro chip, Titanium design", "image": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=200&q=80",
     "rating_rate": 4.9, "rating_count": 1200},
    {"title": "iPhone 15", "price": 899.00, "category": "electronics",
     "description": "A16 Bionic, 48MP camera", "image": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 780},
    {"title": "iPhone 14", "price": 699.00, "category": "electronics",
     "description": "A15 Bionic, dual camera", "image": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 1100},
    {"title": "Samsung Galaxy S24 Ultra", "price": 1199.00, "category": "electronics",
     "description": "AI powered, S Pen included", "image": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 850},
    {"title": "Samsung Galaxy S24", "price": 899.00, "category": "electronics",
     "description": "Galaxy AI, 50MP camera", "image": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 620},
    {"title": "Samsung Galaxy S23 Ultra", "price": 999.00, "category": "electronics",
     "description": "200MP camera, S Pen", "image": "https://images.unsplash.com/photo-1610945415295-d9bbf067e59c?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 940},
    {"title": "Google Pixel 8 Pro", "price": 999.00, "category": "electronics",
     "description": "Google AI, pro camera controls", "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 430},
    {"title": "Google Pixel 8", "price": 699.00, "category": "electronics",
     "description": "Tensor G3, best-in-class camera", "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 380},
    {"title": "OnePlus 12", "price": 799.00, "category": "electronics",
     "description": "Snapdragon 8 Gen 3, 100W charging", "image": "https://images.unsplash.com/photo-1580910051074-3eb694886505?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 510},
    {"title": "Xiaomi 14 Ultra", "price": 999.00, "category": "electronics",
     "description": "Leica optics, 1-inch sensor", "image": "https://images.unsplash.com/photo-1580910051074-3eb694886505?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 290},
    {"title": "iPad Pro 12.9", "price": 1099.00, "category": "electronics",
     "description": "M2 chip, Liquid Retina XDR", "image": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=200&q=80",
     "rating_rate": 4.9, "rating_count": 540},
    {"title": "iPad Air", "price": 599.00, "category": "electronics",
     "description": "M1 chip, lightweight design", "image": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 320},
    {"title": "Samsung Galaxy Tab S9", "price": 799.00, "category": "electronics",
     "description": "Snapdragon 8 Gen 2, S Pen", "image": "https://images.unsplash.com/photo-1585790050230-5dd28404ccb9?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 260},

    # ── Electronics: laptops & computers ───────────────────────────────
    {"title": "MacBook Pro 14 inch", "price": 1999.00, "category": "electronics",
     "description": "M3 Pro chip", "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=200&q=80",
     "rating_rate": 4.9, "rating_count": 950},
    {"title": "MacBook Pro 16 inch", "price": 2499.00, "category": "electronics",
     "description": "M3 Max chip, 36GB RAM", "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=200&q=80",
     "rating_rate": 4.9, "rating_count": 410},
    {"title": "MacBook Air 13", "price": 1099.00, "category": "electronics",
     "description": "M3 chip, fanless design", "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 680},
    {"title": "Dell XPS 15", "price": 1899.00, "category": "electronics",
     "description": "Intel Core Ultra 7, OLED", "image": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 340},
    {"title": "Dell XPS 13", "price": 1299.00, "category": "electronics",
     "description": "Compact, InfinityEdge display", "image": "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 420},
    {"title": "HP Spectre x360", "price": 1499.00, "category": "electronics",
     "description": "2-in-1 convertible, touch", "image": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 250},
    {"title": "Lenovo ThinkPad X1 Carbon", "price": 1699.00, "category": "electronics",
     "description": "Lightweight business laptop", "image": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 380},
    {"title": "ASUS ROG Zephyrus G14", "price": 1599.00, "category": "electronics",
     "description": "RTX 4060 gaming laptop", "image": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 490},
    {"title": "MSI Gaming Laptop GF63", "price": 999.00, "category": "electronics",
     "description": "RTX 3050, 144Hz display", "image": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 720},

    # ── Electronics: wearables, audio & accessories ────────────────────
    {"title": "Apple Watch Ultra 2", "price": 799.00, "category": "electronics",
     "description": "Titanium, 49mm, dual GPS", "image": "https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 520},
    {"title": "Apple Watch Series 9", "price": 399.00, "category": "electronics",
     "description": "S9 chip, always-on display", "image": "https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 880},
    {"title": "Samsung Galaxy Watch 6", "price": 299.00, "category": "electronics",
     "description": "Health tracking, AMOLED", "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 640},
    {"title": "AirPods Pro 2", "price": 249.00, "category": "electronics",
     "description": "Active noise cancellation", "image": "https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 1500},
    {"title": "AirPods Max", "price": 549.00, "category": "electronics",
     "description": "Over-ear, spatial audio", "image": "https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 410},
    {"title": "Sony WH-1000XM5", "price": 399.00, "category": "electronics",
     "description": "Best-in-class ANC headphones", "image": "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=200&q=80",
     "rating_rate": 4.9, "rating_count": 980},
    {"title": "JBL Flip 6 Speaker", "price": 129.00, "category": "electronics",
     "description": "Portable waterproof speaker", "image": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 760},
    {"title": "PlayStation 5", "price": 499.00, "category": "electronics",
     "description": "8K capable, SSD storage", "image": "https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?w=200&q=80",
     "rating_rate": 4.9, "rating_count": 2300},

    # ── Men's clothing ──────────────────────────────────────────────────
    {"title": "Mens Cotton Jacket", "price": 55.99, "category": "men's clothing",
     "description": "Great outerwear jacket", "image": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 500},
    {"title": "Mens Casual Slim Fit T-Shirts", "price": 22.99, "category": "men's clothing",
     "description": "Pack of 3, 100% cotton", "image": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 840},
    {"title": "Mens Denim Jacket", "price": 89.99, "category": "men's clothing",
     "description": "Classic blue denim", "image": "https://images.unsplash.com/photo-1551537482-f2075a1d41f2?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 320},
    {"title": "Mens Leather Jacket", "price": 149.99, "category": "men's clothing",
     "description": "Genuine leather, biker style", "image": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 190},
    {"title": "Mens Oxford Shirt", "price": 39.99, "category": "men's clothing",
     "description": "Formal button-down shirt", "image": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 450},
    {"title": "Mens Chino Pants", "price": 49.99, "category": "men's clothing",
     "description": "Slim fit, stretch cotton", "image": "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 380},
    {"title": "Mens Jeans", "price": 59.99, "category": "men's clothing",
     "description": "Regular fit, straight leg", "image": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 610},
    {"title": "Mens Hoodie", "price": 44.99, "category": "men's clothing",
     "description": "Fleece-lined pullover hoodie", "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 730},
    {"title": "Mens Sweatshirt", "price": 39.99, "category": "men's clothing",
     "description": "Crew neck, cotton blend", "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 280},
    {"title": "Mens Polo Shirt", "price": 34.99, "category": "men's clothing",
     "description": "Classic polo, breathable", "image": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 390},
    {"title": "Mens Suit Blazer", "price": 189.99, "category": "men's clothing",
     "description": "Tailored fit, wool blend", "image": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 160},
    {"title": "Mens Winter Coat", "price": 129.99, "category": "men's clothing",
     "description": "Insulated parka for winter", "image": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 200},

    # ── Women's clothing ────────────────────────────────────────────────
    {"title": "Women's Floral Summer Dress", "price": 49.99, "category": "women's clothing",
     "description": "Lightweight, floral print", "image": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 480},
    {"title": "Women's Maxi Skirt", "price": 39.99, "category": "women's clothing",
     "description": "Elegant flowing maxi skirt", "image": "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 310},
    {"title": "Women's Blouse", "price": 29.99, "category": "women's clothing",
     "description": "Elegant silk blouse", "image": "https://images.unsplash.com/photo-1551163943-3f6a855d1153?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 520},
    {"title": "Women's Cardigan", "price": 44.99, "category": "women's clothing",
     "description": "Knitted cardigan, open front", "image": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 260},
    {"title": "Women's Trench Coat", "price": 109.99, "category": "women's clothing",
     "description": "Classic belted trench coat", "image": "https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 180},
    {"title": "Women's Yoga Leggings", "price": 34.99, "category": "women's clothing",
     "description": "High waist, moisture wicking", "image": "https://images.unsplash.com/photo-1506629082955-511b1aa562c8?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 690},
    {"title": "Women's Denim Jeans", "price": 54.99, "category": "women's clothing",
     "description": "Skinny fit, stretch denim", "image": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 420},
    {"title": "Women's Evening Gown", "price": 159.99, "category": "women's clothing",
     "description": "Floor-length formal gown", "image": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 140},
    {"title": "Women's Sneakers", "price": 69.99, "category": "women's clothing",
     "description": "Comfortable athletic sneakers", "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 560},
    {"title": "Women's Heels", "price": 79.99, "category": "women's clothing",
     "description": "Elegant high heels", "image": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 330},
    {"title": "Women's Handbag", "price": 89.99, "category": "women's clothing",
     "description": "Leather shoulder bag", "image": "https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 470},
    {"title": "Women's Scarf", "price": 24.99, "category": "women's clothing",
     "description": "Silk scarf, versatile style", "image": "https://images.unsplash.com/photo-1601924994987-69e26d50dc26?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 210},

    # ── Jewelery ─────────────────────────────────────────────────────────
    {"title": "Gold Diamond Ring", "price": 899.00, "category": "jewelery",
     "description": "18K gold with 1 carat diamond", "image": "https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 230},
    {"title": "Silver Pendant Necklace", "price": 129.00, "category": "jewelery",
     "description": "Sterling silver pendant", "image": "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 340},
    {"title": "Gold Chain Necklace", "price": 499.00, "category": "jewelery",
     "description": "18K gold chain", "image": "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 280},
    {"title": "Diamond Stud Earrings", "price": 699.00, "category": "jewelery",
     "description": "0.5 carat each, 14K white gold", "image": "https://images.unsplash.com/photo-1630019852942-f89202989a59?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 190},
    {"title": "Gold Hoop Earrings", "price": 199.00, "category": "jewelery",
     "description": "Classic gold hoops", "image": "https://images.unsplash.com/photo-1630019852942-f89202989a59?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 420},
    {"title": "Silver Bracelet", "price": 149.00, "category": "jewelery",
     "description": "Sterling silver bangle", "image": "https://images.unsplash.com/photo-1573408301185-9146fe634ad0?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 250},
    {"title": "Gold Wedding Band", "price": 799.00, "category": "jewelery",
     "description": "18K gold wedding band", "image": "https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 160},
    {"title": "Pearl Necklace", "price": 349.00, "category": "jewelery",
     "description": "Freshwater pearl strand", "image": "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 180},
    {"title": "Sapphire Ring", "price": 1199.00, "category": "jewelery",
     "description": "Blue sapphire in white gold", "image": "https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 120},
    {"title": "Emerald Pendant", "price": 849.00, "category": "jewelery",
     "description": "Emerald set in gold", "image": "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 95},
    {"title": "Men's Gold Ring", "price": 399.00, "category": "jewelery",
     "description": "Heavy men's gold ring", "image": "https://images.unsplash.com/photo-1605100804763-247f67b3557e?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 130},

    # ── Watches ──────────────────────────────────────────────────────────
    {"title": "Rolex Submariner", "price": 9500.00, "category": "watches",
     "description": "Automatic, stainless steel", "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=200&q=80",
     "rating_rate": 4.9, "rating_count": 95},
    {"title": "Casio G-Shock", "price": 129.00, "category": "watches",
     "description": "Rugged digital watch", "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 640},
    {"title": "Seiko Automatic Watch", "price": 349.00, "category": "watches",
     "description": "Japanese automatic movement", "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 310},
    {"title": "Fossil Chronograph", "price": 189.00, "category": "watches",
     "description": "Stainless steel chronograph", "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 270},
    {"title": "Daniel Wellington Classic", "price": 199.00, "category": "watches",
     "description": "Minimalist leather band", "image": "https://images.unsplash.com/photo-1522312346375-d1a52e2b99b3?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 450},
    {"title": "Smart Watch Fitness Tracker", "price": 79.99, "category": "watches",
     "description": "Heart rate, step tracking", "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=200&q=80",
     "rating_rate": 4.3, "rating_count": 890},

    # ── Home & Kitchen ───────────────────────────────────────────────────
    {"title": "Espresso Coffee Machine", "price": 399.00, "category": "home",
     "description": "15-bar pump espresso maker", "image": "https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 520},
    {"title": "Air Fryer 5.5L", "price": 149.00, "category": "home",
     "description": "Oil-free cooking, digital panel", "image": "https://images.unsplash.com/photo-1593642632823-8f785ba67e45?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 780},
    {"title": "Robot Vacuum Cleaner", "price": 299.00, "category": "home",
     "description": "Smart mapping, self-charging", "image": "https://images.unsplash.com/photo-1585790050230-5dd28404ccb9?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 430},
    {"title": "LED Desk Lamp", "price": 49.99, "category": "home",
     "description": "Rechargeable, dimmable", "image": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 610},
    {"title": "Electric Kettle", "price": 39.99, "category": "home",
     "description": "Stainless steel, rapid boil", "image": "https://images.unsplash.com/photo-1594385208974-2e75f8d7bb48?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 540},
    {"title": "Stainless Steel Cookware Set", "price": 189.00, "category": "home",
     "description": "10-piece cookware set", "image": "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 380},
    {"title": "Memory Foam Pillow", "price": 59.99, "category": "home",
     "description": "Ergonomic cervical pillow", "image": "https://images.unsplash.com/photo-1522778034537-8edc418d2616?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 690},
    {"title": "Bed Sheets Set", "price": 79.99, "category": "home",
     "description": "Egyptian cotton 4-piece set", "image": "https://images.unsplash.com/photo-1584100936595-c0654b55a2e6?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 450},

    # ── Sports & Outdoors ────────────────────────────────────────────────
    {"title": "Yoga Mat", "price": 34.99, "category": "sports",
     "description": "Non-slip, eco-friendly", "image": "https://images.unsplash.com/photo-1592432678016-e910b452f9a2?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 720},
    {"title": "Dumbbell Set 20kg", "price": 159.00, "category": "sports",
     "description": "Adjustable dumbbells", "image": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 380},
    {"title": "Treadmill", "price": 899.00, "category": "sports",
     "description": "Foldable home treadmill", "image": "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 210},
    {"title": "Exercise Bike", "price": 499.00, "category": "sports",
     "description": "Indoor cycling bike", "image": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 250},
    {"title": "Camping Tent", "price": 149.00, "category": "sports",
     "description": "4-person waterproof tent", "image": "https://images.unsplash.com/photo-1478131143081-80f7f84ca84d?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 330},

    # ── Beauty & Personal Care ──────────────────────────────────────────
    {"title": "Hair Dryer", "price": 89.99, "category": "beauty",
     "description": "Ionic, 1800W dryer", "image": "https://images.unsplash.com/photo-1522337660859-02fbefca4702?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 480},
    {"title": "Electric Toothbrush", "price": 79.99, "category": "beauty",
     "description": "Sonic brush, 5 modes", "image": "https://images.unsplash.com/photo-1559599189-fe84dea4eb79?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 390},
    {"title": "Facial Cleanser Set", "price": 49.99, "category": "beauty",
     "description": "3-step skincare set", "image": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 520},
    {"title": "Perfume - Eau de Parfum", "price": 119.99, "category": "beauty",
     "description": "Long-lasting floral scent", "image": "https://images.unsplash.com/photo-1541643600914-78b084683601?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 680},

    # ── Books ────────────────────────────────────────────────────────────
    {"title": "The Alchemist", "price": 16.99, "category": "books",
     "description": "Paulo Coelho bestseller", "image": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 1200},
    {"title": "Atomic Habits", "price": 22.99, "category": "books",
     "description": "James Clear, habit guide", "image": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&q=80",
     "rating_rate": 4.8, "rating_count": 3400},
    {"title": "Rich Dad Poor Dad", "price": 18.99, "category": "books",
     "description": "Robert Kiyosaki, finance classic", "image": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 2800},
    {"title": "48 Laws of Power", "price": 24.99, "category": "books",
     "description": "Robert Greene, strategy classic", "image": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 1900},
    {"title": "Elon Musk Biography", "price": 28.99, "category": "books",
     "description": "Walter Isaacson biography", "image": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 1500},

    # ── Extra (to reach ~100) ────────────────────────────────────────────
    {"title": "Mens Running Shoes", "price": 89.99, "category": "men's clothing",
     "description": "Lightweight cushioned runners", "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 830},
    {"title": "Wireless Gaming Mouse", "price": 69.99, "category": "electronics",
     "description": "16000 DPI, RGB gaming mouse", "image": "https://images.unsplash.com/photo-1527814050087-3793815479db?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 540},
    {"title": "Mechanical Gaming Keyboard", "price": 129.99, "category": "electronics",
     "description": "RGB backlit mechanical keys", "image": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 620},
    {"title": "Women's Perfume Gift Set", "price": 89.99, "category": "beauty",
     "description": "3-piece fragrance set", "image": "https://images.unsplash.com/photo-1523293182086-7651a899d37f?w=200&q=80",
     "rating_rate": 4.6, "rating_count": 410},
    {"title": "Office Desk Chair", "price": 249.00, "category": "home",
     "description": "Ergonomic mesh office chair", "image": "https://images.unsplash.com/photo-1505798577917-a65157d3320a?w=200&q=80",
     "rating_rate": 4.4, "rating_count": 290},
    {"title": "Digital Camera Mirrorless", "price": 1299.00, "category": "electronics",
     "description": "24MP mirrorless camera", "image": "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=200&q=80",
     "rating_rate": 4.7, "rating_count": 350},
    {"title": "Portable Bluetooth Speaker", "price": 59.99, "category": "electronics",
     "description": "Waterproof, 20h battery", "image": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=200&q=80",
     "rating_rate": 4.5, "rating_count": 780},
]

STORES = [
    {"name": "موبايلي - قنا", "governorate": "قنا", "lat": 26.1551, "lon": 32.7160, "phone": "01001111222",
     "products_csv": "phone,mobile,iphone,samsung,موبايل"},
    {"name": "تك وورلد - الأقصر", "governorate": "الأقصر", "lat": 25.6872, "lon": 32.6396, "phone": "01002222333",
     "products_csv": "phone,laptop,monitor,موبايل,لابتوب"},
    {"name": "القاهرة للتقنية", "governorate": "القاهرة", "lat": 30.0444, "lon": 31.2357, "phone": "01003333444",
     "products_csv": "phone,laptop,monitor,gaming,موبايل,لابتوب"},
    {"name": "الإسكندرية تك", "governorate": "الإسكندرية", "lat": 31.2001, "lon": 29.9187, "phone": "01004444555",
     "products_csv": "phone,laptop,tablet,موبايل,لابتوب"},
    {"name": "زكي للتكنولوجيا", "governorate": "الجيزة", "lat": 30.0131, "lon": 31.2089, "phone": "01552424553",
     "products_csv": "phone,laptop,iphone,samsung,موبايل,لابتوب"},
    {"name": "فاشون هاوس - قنا", "governorate": "قنا", "lat": 26.1600, "lon": 32.7200, "phone": "01005555666",
     "products_csv": "jacket,shirt,clothing,جاكيت,ملابس,قميص"},
    {"name": "ستايل هاوس - القاهرة", "governorate": "القاهرة", "lat": 30.0444, "lon": 31.2357, "phone": "01006666777",
     "products_csv": "jacket,shirt,tshirt,clothing,جاكيت,تيشرت"},
    {"name": "مودا ستور - الإسكندرية", "governorate": "الإسكندرية", "lat": 31.2001, "lon": 29.9187, "phone": "01007777888",
     "products_csv": "jacket,shirt,women clothing,ملابس,موضة"},
    {"name": "جولدن جول - قنا", "governorate": "قنا", "lat": 26.1580, "lon": 32.7140, "phone": "01008888999",
     "products_csv": "ring,gold,jewelry,earring,خاتم,ذهب,مجوهرات"},
    {"name": "زكي للمجوهرات", "governorate": "الجيزة", "lat": 30.0131, "lon": 31.2089, "phone": "01552424553",
     "products_csv": "ring,necklace,earring,gold,silver,خاتم,قلادة,ذهب"},
    {"name": "دياموند هاوس", "governorate": "القاهرة", "lat": 30.0444, "lon": 31.2357, "phone": "01009999000",
     "products_csv": "ring,diamond,gold,خاتم,ألماس,ذهب"},
    {"name": "توب تك - أسيوط", "governorate": "أسيوط", "lat": 27.1809, "lon": 31.1837, "phone": "01001111000",
     "products_csv": "phone,laptop,monitor,موبايل"},
    {"name": "إلكترو سوق", "governorate": "المنيا", "lat": 28.1099, "lon": 30.7503, "phone": "01002222111",
     "products_csv": "electronics,phone,laptop,الكترونيات"},
]


async def seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    embeddings = get_embedding_service()
    texts = [product_embedding_text(ProductModel(**p)) for p in PRODUCTS]
    vectors: list[list[float]] = []
    print(f"🔢 Computing {len(texts)} embeddings (Cohere)...")
    try:
        vectors = await embeddings.embed_documents(texts)
    except Exception as exc:
        print(f"⚠️  Embeddings skipped: {exc}")

    from sqlalchemy.ext.asyncio import async_sessionmaker

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        for product, vector in zip(PRODUCTS, vectors):
            product["embedding"] = vector
        db.add_all([ProductModel(**p) for p in PRODUCTS])
        db.add_all([StoreModel(**s) for s in STORES])
        await db.commit()

    await engine.dispose()
    print(f"✅ Seeded {len(PRODUCTS)} products and {len(STORES)} stores.")


if __name__ == "__main__":
    asyncio.run(seed())