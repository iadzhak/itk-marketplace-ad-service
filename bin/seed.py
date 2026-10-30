import asyncio
import json
import logging
import os
import pathlib
import random

import httpx

logger = logging.getLogger("seed")

# Ходим через nginx фронтенда, тот же origin, что и у SPA.
BASE_URL = os.getenv("MARKETPLACE_URL", "http://localhost:8080")
SEED_FILE = pathlib.Path(
    os.getenv("SEED_FILE", pathlib.Path(__file__).resolve().parent.parent / "seed.json")
)


def load_seed() -> tuple[list[dict], list[str], list[dict]]:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    return data["users"], data["cities"], data["items"]


async def register(client: httpx.AsyncClient, user: dict) -> None:
    resp = await client.post("/api/auth/register", json=user)
    if resp.status_code == 201:
        logger.info(
            "registered user %s (user_id=%s)", user["email"], resp.json()["user_id"]
        )
    elif resp.status_code == 409:
        logger.info("user %s already exists, skipping", user["email"])
    else:
        resp.raise_for_status()


async def login(client: httpx.AsyncClient, user: dict) -> str:
    resp = await client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    resp.raise_for_status()
    tokens = resp.json()
    logger.info("logged in %s", user["email"])
    return tokens["access_token"]


async def fetch_me(client: httpx.AsyncClient, token: str) -> dict:
    resp = await client.get(
        "/api/auth/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def create_ad(client: httpx.AsyncClient, token: str, ad: dict) -> dict:
    resp = await client.post(
        "/api/ads",
        headers={"Authorization": f"Bearer {token}"},
        json=ad,
    )
    resp.raise_for_status()
    return resp.json()


async def list_ads(client: httpx.AsyncClient, limit: int = 100) -> dict:
    resp = await client.get("/api/ads", params={"limit": limit})
    resp.raise_for_status()
    return resp.json()


async def list_my_ads(client: httpx.AsyncClient, token: str) -> dict:
    resp = await client.get(
        "/api/ads/my",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


async def get_ad(client: httpx.AsyncClient, ad_id: int) -> dict:
    resp = await client.get(f"/api/ads/{ad_id}")
    resp.raise_for_status()
    return resp.json()


async def update_ad(
    client: httpx.AsyncClient,
    token: str,
    ad_id: int,
    payload: dict,
) -> dict:
    resp = await client.put(
        f"/api/ads/{ad_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


async def delete_ad(client: httpx.AsyncClient, token: str, ad_id: int) -> None:
    resp = await client.delete(
        f"/api/ads/{ad_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()


async def search(client: httpx.AsyncClient, **params) -> dict:
    resp = await client.get("/api/search", params=params)
    resp.raise_for_status()
    return resp.json()


async def suggest(client: httpx.AsyncClient, prefix: str) -> dict:
    resp = await client.get("/api/search/suggest", params={"q": prefix})
    resp.raise_for_status()
    return resp.json()


ADS_PER_USER = int(os.getenv("SEED_ADS_PER_USER", "40"))


def _build_ad(item: dict, cities: list[str]) -> dict:
    title = item["title"]
    base_price = item["price"]
    category = item["category"]
    jitter = int(base_price * 0.05)
    return {
        "title": title,
        "description": f"{title}. В отличном состоянии, есть "
        f"все документы, возможен торг.",
        "price": max(0, base_price + random.randint(-jitter, jitter)),
        "category": category,
        "city": random.choice(cities),
    }


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s"
    )
    random.seed(42)

    users, cities, items = load_seed()
    logger.info(
        "loaded %s users, %s cities, %s items from %s",
        len(users),
        len(cities),
        len(items),
        SEED_FILE,
    )
    logger.info("using base url %s", BASE_URL)

    async with httpx.AsyncClient(
        base_url=BASE_URL, timeout=10.0, follow_redirects=True
    ) as client:
        logger.info("=== auth: register + login ===")
        for user in users:
            await register(client, user)

        tokens: dict[str, str] = {}
        for user in users:
            token = await login(client, user)
            tokens[user["email"]] = token
            me = await fetch_me(client, token)
            logger.info("/auth/users/me → %s", me)

        total_needed = len(users) * ADS_PER_USER
        if total_needed > len(items):
            raise RuntimeError(
                f"need {total_needed} unique items but only {len(items)} "
                f"are defined in {SEED_FILE}; "
                f"reduce SEED_ADS_PER_USER or add more items"
            )
        shuffled = items.copy()
        random.shuffle(shuffled)

        logger.info(
            "=== ads: create %s per user (%s total unique) ===",
            ADS_PER_USER,
            total_needed,
        )
        created_by_user: dict[str, list[dict]] = {u["email"]: [] for u in users}
        for i, user in enumerate(users):
            token = tokens[user["email"]]
            user_items = shuffled[i * ADS_PER_USER : (i + 1) * ADS_PER_USER]
            for item in user_items:
                ad = await create_ad(client, token, _build_ad(item, cities))
                created_by_user[user["email"]].append(ad)
            logger.info(
                "created %s ads for %s",
                len(created_by_user[user["email"]]),
                user["email"],
            )

        logger.info("=== ads: read ===")
        all_ads = await list_ads(client, limit=100)
        logger.info(
            "GET /ads → total=%s, items=%s", all_ads["total"], len(all_ads["items"])
        )

        for user in users:
            my = await list_my_ads(client, tokens[user["email"]])
            logger.info("GET /ads/my (%s) → total=%s", user["email"], my["total"])

        first_email = users[0]["email"]
        first_ad = created_by_user[first_email][0]
        fetched = await get_ad(client, first_ad["id"])
        logger.info("GET /ads/%s → %s", first_ad["id"], fetched["title"])

        logger.info("=== ads: update + delete ===")
        updated = await update_ad(
            client,
            tokens[first_email],
            first_ad["id"],
            {
                "price": fetched["price"] + 10000,
                "title": fetched["title"] + " (обновлено)",
            },
        )
        logger.info("PUT /ads/%s → price=%s", updated["id"], updated["price"])

        last_ad = created_by_user[first_email][-1]
        await delete_ad(client, tokens[first_email], last_ad["id"])
        logger.info("DELETE /ads/%s → archived", last_ad["id"])

        logger.info("=== search: waiting for eventual consistency ===")
        await asyncio.sleep(3)

        res = await search(client, q="macbook")
        logger.info(
            "GET /search?q=macbook → total=%s, first=%s",
            res["total"],
            res["items"][0]["title"] if res["items"] else None,
        )

        res = await search(client, category="Автомобили", sort="price_desc")
        logger.info(
            "GET /search?category=Автомобили&sort=price_desc → total=%s",
            res["total"],
        )

        res = await search(client, min_price=10000, max_price=50000, sort="price_asc")
        logger.info(
            "GET /search?min_price=10000&max_price=50000&sort=price_asc → total=%s",
            res["total"],
        )

        sug = await suggest(client, "Ma")
        logger.info("GET /search/suggest?q=Ma → %s", sug["suggestions"])

        logger.info("=== seed complete ===")


if __name__ == "__main__":
    asyncio.run(main())
