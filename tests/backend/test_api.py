"""API contract tests against the loaded fixture pipeline output."""


def test_health(client) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_alert_page_is_ranked_and_paged(client) -> None:
    page = client.get("/alerts", params={"limit": 10}).json()
    assert page["total"] == 44 and page["limit"] == 10 and len(page["items"]) == 10
    ranks = [a["rank"] for a in page["items"]]
    assert ranks == list(range(1, 11))
    first = page["items"][0]
    assert {"timestep", "community_id", "severity", "has_network_layer", "model_score"} <= set(first)


def test_alert_filters(client) -> None:
    net = client.get("/alerts", params={"network_required": True, "limit": 500}).json()
    assert net["items"] and all(a["has_network_layer"] for a in net["items"])
    high = client.get("/alerts", params={"min_score": 0.5, "limit": 500}).json()
    assert all(a["composite_score"] >= 0.5 for a in high["items"])
    by_anomaly = client.get("/alerts", params={"sort": "anomaly", "limit": 500}).json()["items"]
    scores = [a["anomaly_score"] for a in by_anomaly]
    assert scores == sorted(scores, reverse=True)
    assert client.get("/alerts", params={"sort": "bogus"}).status_code == 422


def test_alert_detail_has_evidence(client) -> None:
    top = client.get("/alerts", params={"limit": 1}).json()["items"][0]
    detail = client.get(f"/alerts/{top['elliptic_tx_id']}").json()
    assert detail["evidence_text"].startswith("Rank 1 alert")
    assert detail["shap_reasons"] and len(detail["shap_reasons"]) == 5
    assert all(i["provenance"] in {"real", "modeled"} for i in detail["evidence_items"])
    assert client.get("/alerts/1").status_code == 404


def test_graph_and_community(client) -> None:
    top = client.get("/alerts", params={"limit": 1}).json()["items"][0]
    graph = client.get(f"/graph/{top['elliptic_tx_id']}", params={"depth": 2}).json()
    assert graph["nodes"][0]["elliptic_tx_id"] == top["elliptic_tx_id"]
    assert graph["edges"]
    ids = {n["elliptic_tx_id"] for n in graph["nodes"]}
    assert all(e["source_tx_id"] in ids and e["target_tx_id"] in ids for e in graph["edges"])

    communities = client.get("/communities", params={"limit": 5}).json()
    assert communities
    detail = client.get(f"/communities/{communities[0]['community_id']}").json()
    assert detail["member_tx_ids"]


def test_stats_threats_pipeline(client) -> None:
    stats = client.get("/stats/summary").json()
    assert stats["total_transactions"] == 2000 and stats["total_alerts"] == 44
    threats = client.get("/threats/overview").json()
    tiers = sum(threats[k] for k in ("critical_count", "high_count", "medium_count", "low_count"))
    assert tiers == 44 and threats["alerts_per_timestep"]
    assert client.get("/pipeline/status").json()["status"] == "complete"
    assert "precision_at_k" in client.get("/pipeline/metrics").json()
