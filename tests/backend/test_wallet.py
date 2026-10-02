"""Wallet, address, IP and metadata endpoints on the fixture pipeline."""


def test_wallet_alerts_ranked(client) -> None:
    page = client.get("/entities", params={"limit": 5}).json()
    assert page["total"] > 0
    assert [e["rank"] for e in page["items"]] == list(range(1, len(page["items"]) + 1))
    scores = [e["risk_score"] for e in page["items"]]
    assert scores == sorted(scores, reverse=True)
    assert client.get("/entities", params={"sort": "nope"}).status_code == 422


def test_wallet_detail_and_graph(client) -> None:
    top = client.get("/entities", params={"limit": 1}).json()["items"][0]
    detail = client.get(f"/entities/{top['entity_id']}").json()
    assert detail["evidence_text"] and detail["evidence_items"]
    assert detail["addresses"] and detail["transactions"] and detail["ips"]
    graph = client.get(f"/entities/{top['entity_id']}/graph").json()
    kinds = {n["kind"] for n in graph["nodes"]}
    assert {"entity", "address", "tx", "ip"} <= kinds
    ids = {n["id"] for n in graph["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
    assert client.get("/entities/999999999").status_code == 404


def test_address_and_ip_lookup(client) -> None:
    top = client.get("/entities", params={"limit": 1}).json()["items"][0]
    detail = client.get(f"/entities/{top['entity_id']}").json()
    address = detail["addresses"][0]["address"]
    info = client.get(f"/addresses/{address}").json()
    assert info["entity"]["entity_id"] == top["entity_id"] and info["transactions"]
    ip = detail["ips"][0]["ip"]
    ip_info = client.get(f"/ips/{ip}").json()
    assert ip_info["transactions"] and ip_info["entities"]


def test_alert_detail_carries_metadata(client) -> None:
    page = client.get("/alerts", params={"limit": 500}).json()["items"]
    with_meta = [a for a in page if client.get(f"/metadata/{a['elliptic_tx_id']}").status_code == 200]
    assert with_meta
    detail = client.get(f"/alerts/{with_meta[0]['elliptic_tx_id']}").json()
    meta = detail["metadata"]
    assert {"txid", "src_ip", "src_port", "dst_port", "entity_id", "entity_rank"} <= set(meta)
