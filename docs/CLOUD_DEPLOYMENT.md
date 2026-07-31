# Bulut kurulumu

Tam panel GitHub Pages üzerinde çalışamaz; Pages statik dosya sunar. Uygulama, zamanlayıcı ve SQLite veritabanı kalıcı diskli tek Railway servisi olarak çalışır. GitHub deposu kaynak ve otomatik dağıtım noktasıdır.

## Railway kurulumu

1. Railway hesabına GitHub ile giriş yap.
2. `ozcanr17/firsat_radar` deposundan yeni servis oluştur.
3. Servise bir volume ekle ve bağlama yolunu `/data` yap.
4. `.env.railway.example` içindeki değişkenleri servise ekle.
5. `FIRSAT_RADAR_ADMIN_PASSWORD` için uzun ve benzersiz bir parola belirle.
6. Servis ayarlarından herkese açık HTTPS alan adı üret.
7. Alan adının hedef portuyla `PORT` değişkenini aynı değere ayarla. Mevcut üretim servisi `6767` kullanır.
8. `/healthz` adresinin `status: ok` döndürdüğünü doğrula.

Servis tek replica olarak kalmalıdır. Panel ve saatlik bot aynı kalıcı veritabanını kullanır. GitHub `main` dalına gönderilen her değişiklik Railway tarafından yeniden dağıtılır.

## Pazar yeri erişimleri

- Hepsiburada görünür ürün sayfaları üzerinden mevcut politika sınırlarıyla çalışır.
- Amazon Türkiye bağlantısı için Amazon Associates ve Creators API kimlik bilgileri gerekir.
- Trendyol için herkese açık tam katalog araştırma API'si yerine onaylı katalog veya affiliate veri akışı gerekir.
- MediaMarkt için katalog ya da affiliate veri akışı anlaşması gerekir.

Erişim anahtarları GitHub'a yazılmaz. Railway servis değişkenlerinde secret olarak saklanır.
