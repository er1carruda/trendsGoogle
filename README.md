# Google Trends Proxy API

API Flask mínima que atua como proxy para o Google Trends, contornando o bloqueio de IPs de datacenter que o Google aplica a ferramentas de automação como o n8n Cloud.

## Por que existe

O Google Trends não tem API pública. O n8n Cloud opera em IPs de datacenter que o Google bloqueia com 429. Esta API roda na VPS (`ueric.com.br`), cujo IP não é classificado como datacenter, e devolve os dados como JSON limpo para consumo pelo n8n.

## Base URL

```
https://trends.ueric.com.br
```

---

## Endpoints

### `GET /trends`

Retorna a série temporal de interesse de busca para uma keyword.

#### Parâmetros de query

| Parâmetro   | Tipo   | Padrão       | Descrição                                              |
|-------------|--------|--------------|--------------------------------------------------------|
| `keyword`   | string | `nuuvem`     | Termo a consultar no Google Trends                     |
| `geo`       | string | `BR`         | Código de país ISO 3166-1 alpha-2                      |
| `timeframe` | string | `today 12-m` | Janela de tempo (sintaxe pytrends — ver tabela abaixo) |

#### Valores de `timeframe`

| Valor            | Descrição                        |
|------------------|----------------------------------|
| `today 12-m`     | Últimos 12 meses (granularidade semanal) |
| `today 3-m`      | Últimos 3 meses                  |
| `today 1-m`      | Último mês (granularidade diária)|
| `today 5-y`      | Últimos 5 anos                   |
| `2024-01-01 2024-12-31` | Intervalo customizado     |

#### Exemplo de request

```bash
curl "https://trends.ueric.com.br/trends?keyword=nuuvem&geo=BR&timeframe=today%2012-m"
```

#### Exemplo de response

```json
[
  { "date": "2024-05-12", "value": 72, "keyword": "nuuvem" },
  { "date": "2024-05-19", "value": 68, "keyword": "nuuvem" },
  { "date": "2024-05-26", "value": 75, "keyword": "nuuvem" }
]
```

| Campo     | Tipo   | Descrição                                              |
|-----------|--------|--------------------------------------------------------|
| `date`    | string | Data no formato `YYYY-MM-DD`                           |
| `value`   | int    | Índice relativo de interesse (0–100)                   |
| `keyword` | string | Keyword consultada (espelho do parâmetro de entrada)   |

> **Nota:** o valor `100` representa o pico de interesse no período. Não é volume absoluto de buscas — é um índice relativo.

#### Response quando não há dados

```json
[]
```

#### Response de erro

```json
{ "error": "mensagem de erro" }
```

HTTP status `500`.

---

### `GET /health`

Healthcheck do serviço.

```bash
curl https://trends.ueric.com.br/health
```

```json
{ "status": "ok" }
```

---

## Usando no n8n

### Configuração do nó HTTP Request

| Campo          | Valor                                                      |
|----------------|------------------------------------------------------------|
| Method         | `GET`                                                      |
| URL            | `https://trends.ueric.com.br/trends`                       |
| Query Params   | `keyword=nuuvem`, `geo=BR`, `timeframe=today 12-m`         |
| Response Format| `JSON`                                                     |

### Escrevendo no Google Sheets

O response já vem como array de objetos — conecte diretamente ao nó **Google Sheets → Append**.

Mapeamento sugerido:

| Coluna no Sheets | Campo do JSON |
|------------------|---------------|
| Data             | `{{ $json.date }}`    |
| Interesse        | `{{ $json.value }}`   |
| Keyword          | `{{ $json.keyword }}` |

### Schedule recomendado

**1x por dia**, preferencialmente de madrugada. Uso mais intenso (múltiplas keywords em sequência rápida) pode gerar 429 do lado do Google Trends.

---

## Limitações conhecidas

- O índice retornado é **relativo (0–100)**, não volume absoluto de buscas
- Janelas acima de 3 meses têm **granularidade semanal**
- A lib `pytrends` pode quebrar se o Google mudar seus endpoints internos — sem SLA
- Uso intensivo pode gerar 429 mesmo nesta VPS — schedule de 1x/dia mitiga

---

## Infraestrutura

```
n8n Cloud
    └─ HTTP Request → https://trends.ueric.com.br/trends
                              │
                        Caddy (TLS)
                              │
                        trends-api:5000 (Docker)
                              │
                        pytrends → Google Trends
```

- **Container:** `trends-api` — `/opt/google-trends/docker-compose.yml`
- **Caddyfile:** `/opt/n8n/Caddyfile`
- **Código-fonte:** `/opt/google-trends/trends-api/`

## Operação

```bash
# Ver logs
docker logs trends-api -f

# Reiniciar
docker compose -f /opt/google-trends/docker-compose.yml restart

# Rebuild após mudança de código
docker compose -f /opt/google-trends/docker-compose.yml up -d --build
```
