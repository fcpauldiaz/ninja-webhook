# Rejected examples (for manual testing)

## Bad secret
curl -s -X POST http://127.0.0.1:5088/webhook ^
  -H "Content-Type: application/json" ^
  -H "X-Webhook-Secret: wrong" ^
  -d "{\"id\":\"bad-secret-1\",\"symbol\":\"ES1!\",\"action\":\"BUY\",\"orderType\":\"MARKET\",\"quantity\":1}"

## Quantity too high
curl -s -X POST http://127.0.0.1:5088/webhook ^
  -H "Content-Type: application/json" ^
  -H "X-Webhook-Secret: change-me-now" ^
  -d "{\"id\":\"qty-high-1\",\"symbol\":\"ES1!\",\"action\":\"BUY\",\"orderType\":\"MARKET\",\"quantity\":99}"

## Unsupported order type
curl -s -X POST http://127.0.0.1:5088/webhook ^
  -H "Content-Type: application/json" ^
  -H "X-Webhook-Secret: change-me-now" ^
  -d "{\"id\":\"limit-1\",\"symbol\":\"ES1!\",\"action\":\"BUY\",\"orderType\":\"LIMIT\",\"quantity\":1}"

## Duplicate id (send twice quickly)
curl -s -X POST http://127.0.0.1:5088/webhook ^
  -H "Content-Type: application/json" ^
  -H "X-Webhook-Secret: change-me-now" ^
  -d "@buy-es.json"
