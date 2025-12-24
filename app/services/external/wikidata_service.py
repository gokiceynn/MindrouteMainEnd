import httpx


async def find_wikidata_id(place_name: str):
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": place_name,
        "language": "en",
        "format": "json",
    }
    async with httpx.AsyncClient(
        timeout=10,
        headers={
            "User-Agent": "MindRoute/1.0 (https://github.com/silaeraslan; contact: sila@example.com)"
        },
    ) as client:
        r = await client.get(url, params=params)
        if r.status_code == 403:
            print("Wikidata blocked the request (403). Probably User-Agent incorrect.")
            return None
        r.raise_for_status()
        data = r.json()
        if data.get("search"):
            return data["search"][0]["id"]
    return None


async def find_wikidata_details(qid: str):
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    async with httpx.AsyncClient(
        timeout=10,
        headers={
            "User-Agent": "MindRoute/1.0 (https://github.com/silaeraslan; contact: sila@example.com)"
        },
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        entity = data.get("entities", {}).get(qid, {})
        labels = entity.get("labels", {})
        descriptions = entity.get("descriptions", {})
        aliases = entity.get("aliases", {})
        return {
            "labels": labels,
            "descriptions": descriptions,
            "aliases": aliases,
        }


