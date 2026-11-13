# tests/integration/test_moderation.py

from datetime import datetime, timedelta, timezone

import pytest

from app.models.moderation import CommunityBan
from tests.factories import create_community_setup
from tests.helpers import create_test_token, embed_headers

API = "/api/v1/embed"
MOD = "/api/v1/moderation"


def headers(setup, subject=None, role=None):
    token = None
    if subject:
        token = create_test_token(
            secret=setup["secret"],
            issuer=setup["issuer"],
            subject=subject,
            username=subject,
            role=role,
        )
    return embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=token)


def mod(setup):
    return headers(setup, "mod", role="moderator")


async def post_comment(http, setup, subject="alice", content="Hello", thread="anime:1", **extra):
    res = await http.post(
        f"{API}/comments",
        headers=headers(setup, subject),
        json={"thread_id": thread, "title": "T", "source_url": "https://example.com/t", "content": content, **extra},
    )
    assert res.status_code in (200, 201), res.text
    return res.json()


async def thread_items(client, setup, subject=None, thread="anime:1"):
    res = await client.get(f"{API}/comments", params={"thread_id": thread}, headers=headers(setup, subject))
    assert res.status_code == 200, res.text
    return res.json()["items"]


async def hide(client, setup, comment_id):
    res = await client.post(f"{MOD}/comments/{comment_id}/hide", headers=mod(setup), json={"reason_key": "spam"})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/reports"),
        ("get", "/comments"),
        ("get", "/bans"),
        ("get", "/actions"),
    ],
)
async def test_moderation_needs_a_staff_role(client, session, method, path):
    setup = await create_community_setup(session)

    assert (await client.request(method, MOD + path, headers=headers(setup))).status_code in (401, 403)
    assert (await client.request(method, MOD + path, headers=headers(setup, "alice"))).status_code == 403
    assert (await client.request(method, MOD + path, headers=mod(setup))).status_code == 200


@pytest.mark.anyio
async def test_an_unknown_role_is_not_staff(client, session):
    setup = await create_community_setup(session)
    res = await client.get(f"{MOD}/comments", headers=headers(setup, "alice", role="superuser"))
    assert res.status_code == 403


@pytest.mark.anyio
async def test_me_reports_the_role(client, session):
    setup = await create_community_setup(session)
    assert (await client.get(f"{API}/me", headers=mod(setup))).json()["staff_role"] == "moderator"
    assert (await client.get(f"{API}/me", headers=headers(setup, "alice"))).json()["staff_role"] is None


@pytest.mark.anyio
async def test_hidden_comment_shows_only_to_its_author(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Secret text")
    await hide(client, setup, comment["id"])

    for viewer in (None, "bob"):
        (item,) = await thread_items(client, setup, viewer)
        assert item["status"] == "hidden"
        assert item["content"] == ""
        assert item["community_user"] is None
        assert item["community_user_id"] is None

    (own,) = await thread_items(client, setup, "alice")
    assert own["content"] == "Secret text"
    assert own["community_user"]["external_user_id"] == "alice"


@pytest.mark.anyio
async def test_hidden_comment_stays_off_other_peoples_view_of_a_profile(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Secret text")
    await post_comment(client, setup, content="Fine")
    await hide(client, setup, comment["id"])

    params = {"external_user_id": "alice"}
    others = (await client.get(f"{API}/comments/mine", params=params, headers=headers(setup, "bob"))).json()
    assert [c["content"] for c in others["items"]] == ["Fine"]
    assert others["total"] == 1

    anonymous = (await client.get(f"{API}/comments/mine", params=params, headers=headers(setup))).json()
    assert [c["content"] for c in anonymous["items"]] == ["Fine"]

    own = (await client.get(f"{API}/comments/mine", headers=headers(setup, "alice"))).json()
    assert own["total"] == 2


@pytest.mark.anyio
async def test_hidden_comment_cannot_be_reached_by_voting_replying_or_editing(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Secret text")
    await hide(client, setup, comment["id"])
    cid = comment["id"]

    vote = await client.post(f"{API}/comments/{cid}/votes", headers=headers(setup, "bob"), json={"value": 1})
    assert vote.status_code == 404
    assert "Secret" not in vote.text

    reply = await client.post(
        f"{API}/comments",
        headers=headers(setup, "bob"),
        json={"thread_id": "anime:1", "content": "Reply", "parent_comment_id": cid},
    )
    assert reply.status_code == 404

    edit = await client.patch(f"{API}/comments/{cid}", headers=headers(setup, "alice"), json={"content": "Now clean"})
    assert edit.status_code == 400


@pytest.mark.anyio
async def test_restore_brings_a_comment_back_for_everyone(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Actually fine")
    await hide(client, setup, comment["id"])

    res = await client.post(f"{MOD}/comments/{comment['id']}/restore", headers=mod(setup), json={})
    assert res.status_code == 200

    (item,) = await thread_items(client, setup, "bob")
    assert item["content"] == "Actually fine"
    assert item["community_user"]["external_user_id"] == "alice"

    again = await client.post(f"{MOD}/comments/{comment['id']}/restore", headers=mod(setup), json={})
    assert again.status_code == 409


@pytest.mark.anyio
async def test_reports_group_by_comment_and_count_each_person_once(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    url = f"{API}/comments/{comment['id']}/reports"

    for subject, reason in (("bob", "spam"), ("bob", "hate"), ("carol", "harassment")):
        res = await client.post(url, headers=headers(setup, subject), json={"reason": reason})
        assert res.status_code == 204, res.text

    (entry,) = (await client.get(f"{MOD}/reports", headers=mod(setup))).json()["items"]
    assert entry["comment"]["id"] == comment["id"]
    assert sorted(r["reason"] for r in entry["reports"]) == ["harassment", "spam"]


@pytest.mark.anyio
async def test_report_needs_a_signed_in_user_and_a_known_reason(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    url = f"{API}/comments/{comment['id']}/reports"

    assert (await client.post(url, headers=headers(setup), json={"reason": "spam"})).status_code == 401
    assert (await client.post(url, headers=headers(setup, "bob"), json={"reason": "nope"})).status_code == 422


@pytest.mark.anyio
async def test_hiding_resolves_reports_and_dismissing_clears_the_queue(client, session):
    setup = await create_community_setup(session)
    first = await post_comment(client, setup, content="One")
    second = await post_comment(client, setup, content="Two")
    for comment in (first, second):
        await client.post(
            f"{API}/comments/{comment['id']}/reports", headers=headers(setup, "bob"), json={"reason": "spam"}
        )

    await hide(client, setup, first["id"])
    queue = (await client.get(f"{MOD}/reports", headers=mod(setup))).json()
    assert [e["comment"]["id"] for e in queue["items"]] == [second["id"]]

    res = await client.post(
        f"{MOD}/comments/{second['id']}/reports/resolve", headers=mod(setup), json={"status": "dismissed"}
    )
    assert res.status_code == 204
    assert (await client.get(f"{MOD}/reports", headers=mod(setup))).json()["items"] == []


@pytest.mark.anyio
async def test_moderators_can_search_with_everything_visible(client, session):
    setup = await create_community_setup(session)
    hidden = await post_comment(client, setup, content="100% spam", source="bad.example", client="extension")
    await post_comment(client, setup, content="Nice episode", source="good.example", client="extension")
    await hide(client, setup, hidden["id"])

    found = (await client.get(f"{MOD}/comments", params={"source": "bad.example"}, headers=mod(setup))).json()
    assert found["total"] == 1
    (item,) = found["items"]
    assert item["content"] == "100% spam"
    assert item["community_user"]["external_user_id"] == "alice"
    assert item["client"] == "extension"
    assert item["thread"]["unique_id"] == "anime:1"

    # % is plain text in a search, not a wildcard
    assert (await client.get(f"{MOD}/comments", params={"q": "100%"}, headers=mod(setup))).json()["total"] == 1
    assert (await client.get(f"{MOD}/comments", params={"q": "%"}, headers=mod(setup))).json()["total"] == 1
    assert (await client.get(f"{MOD}/comments", params={"status": "visible"}, headers=mod(setup))).json()["total"] == 1


@pytest.mark.anyio
async def test_batch_previews_hides_and_undoes(client, session):
    setup = await create_community_setup(session)
    for i in range(3):
        await post_comment(client, setup, content=f"Bad {i}", source="bad.example", thread=f"anime:{i}")
    await post_comment(client, setup, content="Good", source="good.example")
    batch = {"action": "hide", "source": "bad.example"}

    preview = await client.post(f"{MOD}/comments/batch", headers=mod(setup), json={**batch, "dry_run": True})
    assert preview.json() == {"matched": 3, "changed": 0}
    assert (await thread_items(client, setup, "bob", "anime:0"))[0]["status"] == "visible"

    done = await client.post(f"{MOD}/comments/batch", headers=mod(setup), json=batch)
    assert done.json() == {"matched": 3, "changed": 3}
    assert (await thread_items(client, setup, "bob", "anime:0"))[0]["status"] == "hidden"
    statuses = [c["status"] for c in await thread_items(client, setup, "bob", "anime:1")]
    assert statuses == ["hidden", "visible"] or statuses == ["visible", "hidden"]

    log = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()
    assert log["total"] == 1

    undone = await client.post(
        f"{MOD}/comments/batch", headers=mod(setup), json={"action": "restore", "source": "bad.example"}
    )
    assert undone.json() == {"matched": 3, "changed": 3}
    assert (await thread_items(client, setup, "bob", "anime:0"))[0]["content"] == "Bad 0"


@pytest.mark.anyio
async def test_batch_without_a_filter_is_refused(client, session):
    setup = await create_community_setup(session)
    await post_comment(client, setup)

    res = await client.post(f"{MOD}/comments/batch", headers=mod(setup), json={"action": "hide"})
    assert res.status_code == 422
    assert (await thread_items(client, setup))[0]["status"] == "visible"


@pytest.mark.anyio
async def test_batch_restore_leaves_comments_the_author_deleted(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, source="bad.example")
    await client.delete(f"{API}/comments/{comment['id']}", headers=headers(setup, "alice"))

    res = await client.post(
        f"{MOD}/comments/batch", headers=mod(setup), json={"action": "restore", "source": "bad.example"}
    )
    assert res.json() == {"matched": 0, "changed": 0}


@pytest.mark.anyio
async def test_a_ban_stops_writing_until_it_is_lifted(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    user_id = comment["community_user_id"]

    ban = await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": user_id, "reason": "abuse"})
    assert ban.status_code == 200, ban.text
    assert ban.json()["expires_at"] is None

    again = await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": user_id})
    assert again.status_code == 409

    alice = headers(setup, "alice")
    blocked = await client.post(f"{API}/comments", headers=alice, json={"thread_id": "anime:1", "content": "Hi"})
    assert blocked.status_code == 403
    assert (await client.patch(f"{API}/comments/{comment['id']}", headers=alice, json={"content": "x"})).status_code == 403
    assert (await client.post(f"{API}/comments/{comment['id']}/votes", headers=alice, json={"value": 1})).status_code == 403
    assert (await client.post(f"{API}/comments/{comment['id']}/reports", headers=alice, json={"reason": "spam"})).status_code == 403
    # Reading, and removing their own words, still work
    assert len(await thread_items(client, setup, "alice")) == 1

    assert len((await client.get(f"{MOD}/bans", headers=mod(setup))).json()["items"]) == 1

    lifted = await client.post(f"{MOD}/bans/{ban.json()['id']}/lift", headers=mod(setup), json={})
    assert lifted.status_code == 200
    assert (await client.get(f"{MOD}/bans", headers=mod(setup))).json()["items"] == []
    await post_comment(client, setup, content="I'm back")

    assert (await client.post(f"{MOD}/bans/{ban.json()['id']}/lift", headers=mod(setup), json={})).status_code == 409


@pytest.mark.anyio
async def test_a_temporary_ban_ends_by_itself(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    user_id = comment["community_user_id"]
    soon = datetime.now(timezone.utc) + timedelta(hours=1)

    ban = await client.post(
        f"{MOD}/bans", headers=mod(setup), json={"community_user_id": user_id, "expires_at": soon.isoformat()}
    )
    assert ban.status_code == 200, ban.text
    blocked = await client.post(
        f"{API}/comments", headers=headers(setup, "alice"), json={"thread_id": "anime:1", "content": "Hi"}
    )
    assert blocked.status_code == 403
    assert "until" in blocked.json()["detail"]

    row = await session.get(CommunityBan, ban.json()["id"])
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await session.commit()

    await post_comment(client, setup, content="Timed out no more")
    assert (await client.get(f"{MOD}/bans", headers=mod(setup))).json()["items"] == []
    assert len((await client.get(f"{MOD}/bans", params={"status": "all"}, headers=mod(setup))).json()["items"]) == 1


@pytest.mark.anyio
async def test_a_ban_must_end_in_the_future_and_state_its_timezone(client, session):
    setup = await create_community_setup(session)
    user_id = (await post_comment(client, setup))["community_user_id"]
    past = datetime.now(timezone.utc) - timedelta(hours=1)

    res = await client.post(
        f"{MOD}/bans", headers=mod(setup), json={"community_user_id": user_id, "expires_at": past.isoformat()}
    )
    assert res.status_code == 400

    naive = await client.post(
        f"{MOD}/bans", headers=mod(setup), json={"community_user_id": user_id, "expires_at": "2099-01-01T00:00:00"}
    )
    assert naive.status_code == 422


@pytest.mark.anyio
async def test_a_locked_thread_takes_no_comments_or_votes_until_unlocked(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)

    lock = await client.post(f"{MOD}/threads/lock", headers=mod(setup), json={"thread_id": "anime:1", "locked": True})
    assert lock.status_code == 200, lock.text
    assert lock.json()["is_locked"] is True

    bob = headers(setup, "bob")
    assert (await client.post(f"{API}/comments", headers=bob, json={"thread_id": "anime:1", "content": "Hi"})).status_code == 403
    assert (await client.post(f"{API}/comments/{comment['id']}/votes", headers=bob, json={"value": 1})).status_code == 403

    await client.post(f"{MOD}/threads/lock", headers=mod(setup), json={"thread_id": "anime:1", "locked": False})
    await post_comment(client, setup, "bob", content="Open again")


@pytest.mark.anyio
async def test_the_log_records_who_did_what(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    await hide(client, setup, comment["id"])

    (entry,) = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    assert entry["action"] == "hide_comment"
    assert entry["reason"] == "Spam"
    assert entry["moderator"]["external_user_id"] == "mod"
    assert entry["target"]["external_user_id"] == "alice"


@pytest.mark.anyio
async def test_moderators_only_reach_their_own_community(client, session):
    ours = await create_community_setup(session)
    await session.commit()
    theirs = await create_community_setup(
        session,
        name="Other",
        slug="other",
        public_key="tfspub_other",
        origin="https://other.example",
        issuer="other-site",
        secret="other-secret",
        owner_email="other@example.com",
    )
    comment = await post_comment(client, theirs, content="Theirs", source="shared.example")
    user_id = comment["community_user_id"]

    assert (await client.post(f"{MOD}/comments/{comment['id']}/hide", headers=mod(ours), json={})).status_code == 404
    assert (await client.post(f"{MOD}/comments/{comment['id']}/restore", headers=mod(ours), json={})).status_code == 404
    assert (await client.post(f"{MOD}/bans", headers=mod(ours), json={"community_user_id": user_id})).status_code == 404
    res = await client.post(f"{MOD}/threads/lock", headers=mod(ours), json={"thread_id": "anime:1", "locked": True})
    assert res.status_code == 404

    batch = await client.post(
        f"{MOD}/comments/batch", headers=mod(ours), json={"action": "hide", "source": "shared.example"}
    )
    assert batch.json() == {"matched": 0, "changed": 0}
    assert (await client.get(f"{MOD}/comments", headers=mod(ours))).json()["total"] == 0

    # A token signed by one community's secret isn't staff in the other
    forged = create_test_token(secret=ours["secret"], issuer=ours["issuer"], subject="mod", role="admin")
    res = await client.get(
        f"{MOD}/comments",
        headers=embed_headers(public_key=theirs["public_key"], origin=theirs["origin"], token=forged),
    )
    assert res.status_code in (401, 403)
    assert (await thread_items(client, theirs))[0]["status"] == "visible"


def admin(setup):
    return headers(setup, "boss", role="admin")


async def report(client, setup, comment_id, subject="bob", reason="spam"):
    res = await client.post(
        f"{API}/comments/{comment_id}/reports", headers=headers(setup, subject), json={"reason": reason}
    )
    assert res.status_code == 204, res.text


@pytest.mark.anyio
async def test_reasons_default_to_generic_ones_and_can_be_replaced(client, session):
    setup = await create_community_setup(session)
    config = (await client.get(f"{API}/config", headers=headers(setup))).json()
    keys = [reason["key"] for reason in config["report_reasons"]]
    assert keys == ["spam", "harassment", "hate", "violence", "personal_info", "sexual", "off_topic", "other"]

    reasons = {"reasons": [{"key": "spam", "label": "Spam"}, {"key": "wrong_episode", "label": "Wrong episode"}]}
    assert (await client.put(f"{MOD}/reasons", headers=mod(setup), json=reasons)).status_code == 403
    assert (await client.put(f"{MOD}/reasons", headers=admin(setup), json=reasons)).status_code == 200

    config = (await client.get(f"{API}/config", headers=headers(setup))).json()
    assert [reason["key"] for reason in config["report_reasons"]] == ["spam", "wrong_episode"]

    comment = await post_comment(client, setup)
    await report(client, setup, comment["id"], reason="wrong_episode")
    res = await client.post(
        f"{API}/comments/{comment['id']}/reports", headers=headers(setup, "carol"), json={"reason": "hate"}
    )
    assert res.status_code == 422


@pytest.mark.anyio
async def test_invalid_reason_lists_are_refused(client, session):
    setup = await create_community_setup(session)

    for reasons in (
        [],
        [{"key": "Has Spaces", "label": "x"}],
        [{"key": "a", "label": "x"}, {"key": "a", "label": "y"}],
    ):
        res = await client.put(f"{MOD}/reasons", headers=admin(setup), json={"reasons": reasons})
        assert res.status_code == 422


@pytest.mark.anyio
async def test_past_reports_keep_their_label_when_a_reason_goes_away(client, session):
    setup = await create_community_setup(session)
    await client.put(
        f"{MOD}/reasons", headers=admin(setup), json={"reasons": [{"key": "bad", "label": "Original label"}]}
    )
    comment = await post_comment(client, setup)
    await report(client, setup, comment["id"], reason="bad")

    await client.put(f"{MOD}/reasons", headers=admin(setup), json={"reasons": [{"key": "new", "label": "New"}]})

    (entry,) = (await client.get(f"{MOD}/reports", headers=mod(setup))).json()["items"]
    assert entry["reports"][0]["reason_label"] == "Original label"


@pytest.mark.anyio
async def test_the_removal_reason_reaches_only_the_author(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Secret text")
    url = f"{MOD}/comments/{comment['id']}/hide"

    assert (await client.post(url, headers=mod(setup), json={"reason_key": "nope"})).status_code == 422
    res = await client.post(url, headers=mod(setup), json={"reason_key": "spam", "note": "Third time this week"})
    assert res.status_code == 200

    (own,) = await thread_items(client, setup, "alice")
    assert own["removal_reason"] == "Spam"
    mine = (await client.get(f"{API}/comments/mine", headers=headers(setup, "alice"))).json()
    assert mine["items"][0]["removal_reason"] == "Spam"

    (other,) = await thread_items(client, setup, "bob")
    assert other["removal_reason"] is None
    assert "Third time" not in str(own)

    (entry,) = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    assert entry["reason"] == "Spam: Third time this week"

    await client.post(f"{MOD}/comments/{comment['id']}/restore", headers=mod(setup), json={})
    (restored,) = await thread_items(client, setup, "alice")
    assert restored["removal_reason"] is None


@pytest.mark.anyio
async def test_remove_and_ban_is_one_step(client, session):
    setup = await create_community_setup(session)
    first = await post_comment(client, setup)
    second = await post_comment(client, setup, content="Again")
    body = {"reason_key": "spam", "ban": True}

    res = await client.post(f"{MOD}/comments/{first['id']}/hide", headers=mod(setup), json=body)
    assert res.status_code == 200, res.text

    bans = (await client.get(f"{MOD}/bans", headers=mod(setup))).json()["items"]
    assert len(bans) == 1
    assert bans[0]["reason"] == "Spam"

    # Already banned: the comment still goes, and the ban they have stands
    res = await client.post(f"{MOD}/comments/{second['id']}/hide", headers=mod(setup), json=body)
    assert res.status_code == 200
    assert len((await client.get(f"{MOD}/bans", headers=mod(setup))).json()["items"]) == 1


@pytest.mark.anyio
async def test_remove_and_ban_with_a_past_expiry_changes_nothing(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    res = await client.post(
        f"{MOD}/comments/{comment['id']}/hide", headers=mod(setup), json={"ban": True, "ban_expires_at": past}
    )
    assert res.status_code == 400
    assert (await thread_items(client, setup))[0]["status"] == "visible"


@pytest.mark.anyio
async def test_the_queue_filters_by_reason_and_sorts(client, session):
    setup = await create_community_setup(session)
    once = await post_comment(client, setup, content="Reported once")
    twice = await post_comment(client, setup, content="Reported twice")
    await report(client, setup, twice["id"], "bob")
    await report(client, setup, twice["id"], "carol")
    await report(client, setup, once["id"], "dave", reason="hate")

    async def queue(**params):
        res = await client.get(f"{MOD}/reports", params=params, headers=mod(setup))
        assert res.status_code == 200, res.text
        return [entry["comment"]["id"] for entry in res.json()["items"]]

    assert await queue() == [once["id"], twice["id"]]
    assert await queue(sort="oldest") == [twice["id"], once["id"]]
    assert await queue(sort="most_reported") == [twice["id"], once["id"]]
    assert await queue(reason="hate") == [once["id"]]


@pytest.mark.anyio
async def test_replies_come_with_what_they_answer(client, session):
    setup = await create_community_setup(session)
    parent = await post_comment(client, setup, "bob", content="The original")
    reply = await post_comment(client, setup, content="The reply", parent_comment_id=parent["id"])
    await report(client, setup, reply["id"], "carol")

    (entry,) = (await client.get(f"{MOD}/reports", headers=mod(setup))).json()["items"]
    assert entry["comment"]["parent"]["content"] == "The original"
    assert entry["comment"]["parent"]["community_user"]["external_user_id"] == "bob"

    items = (await client.get(f"{MOD}/comments", headers=mod(setup))).json()["items"]
    by_content = {item["content"]: item for item in items}
    assert by_content["The reply"]["parent"]["id"] == parent["id"]
    assert by_content["The original"]["parent"] is None

    hidden = await client.post(f"{MOD}/comments/{reply['id']}/hide", headers=mod(setup), json={})
    assert hidden.json()["parent"]["content"] == "The original"


@pytest.mark.anyio
async def test_selected_comments_can_be_acted_on_together(client, session):
    setup = await create_community_setup(session)
    first = await post_comment(client, setup, content="One")
    second = await post_comment(client, setup, content="Two")
    await post_comment(client, setup, content="Three")

    res = await client.post(
        f"{MOD}/comments/batch",
        headers=mod(setup),
        json={"action": "hide", "comment_ids": [first["id"], second["id"]], "reason_key": "spam"},
    )
    assert res.json() == {"matched": 2, "changed": 2}

    items = await thread_items(client, setup, "alice")
    assert sorted(item["status"] for item in items) == ["hidden", "hidden", "visible"]
    assert {item["removal_reason"] for item in items if item["status"] == "hidden"} == {"Spam"}


@pytest.mark.anyio
async def test_the_removed_view_puts_the_latest_removal_first(client, session):
    setup = await create_community_setup(session)
    first = await post_comment(client, setup, content="Older comment")
    second = await post_comment(client, setup, content="Newer comment")
    await hide(client, setup, second["id"])
    await hide(client, setup, first["id"])

    res = await client.get(f"{MOD}/comments", params={"status": "hidden", "sort": "changed"}, headers=mod(setup))
    assert [item["id"] for item in res.json()["items"]] == [first["id"], second["id"]]


@pytest.mark.anyio
async def test_moderators_can_find_a_user_and_see_their_record(client, session):
    setup = await create_community_setup(session)
    removed = await post_comment(client, setup, content="Bad")
    reported = await post_comment(client, setup, content="Borderline")
    await post_comment(client, setup, "bob", content="Fine")
    await hide(client, setup, removed["id"])
    await report(client, setup, reported["id"], "bob")
    user_id = reported["community_user_id"]

    found = (await client.get(f"{MOD}/users", params={"q": "ALI"}, headers=mod(setup))).json()
    assert [user["external_user_id"] for user in found["items"]] == ["alice"]
    assert found["items"][0]["comment_count"] == 2
    assert found["items"][0]["removed_count"] == 1
    assert found["items"][0]["report_count"] == 1
    assert found["items"][0]["is_banned"] is False

    # % is plain text here too
    assert (await client.get(f"{MOD}/users", params={"q": "%"}, headers=mod(setup))).json()["total"] == 0

    ban = await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": user_id, "reason": "Abuse"})
    await client.post(f"{MOD}/bans/{ban.json()['id']}/lift", headers=mod(setup), json={})
    await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": user_id})

    record = (await client.get(f"{MOD}/users/{user_id}", headers=mod(setup))).json()
    assert record["is_banned"] is True
    assert len(record["bans"]) == 2
    assert record["bans"][1]["reason"] == "Abuse"


@pytest.mark.anyio
async def test_notes_stay_between_moderators(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    user_id = comment["community_user_id"]
    url = f"{MOD}/users/{user_id}/notes"

    assert (await client.post(url, headers=headers(setup, "alice"), json={"body": "x"})).status_code == 403
    assert (await client.post(url, headers=mod(setup), json={"body": ""})).status_code == 422

    note = await client.post(url, headers=mod(setup), json={"body": "Warned in October"})
    assert note.status_code == 200, note.text
    assert note.json()["author"]["external_user_id"] == "mod"

    record = (await client.get(f"{MOD}/users/{user_id}", headers=mod(setup))).json()
    assert [n["body"] for n in record["notes"]] == ["Warned in October"]

    for viewer in ("alice", "bob"):
        res = await client.get(f"{API}/comments", params={"thread_id": "anime:1"}, headers=headers(setup, viewer))
        assert "Warned" not in res.text

    assert (await client.delete(f"{MOD}/notes/{note.json()['id']}", headers=mod(setup))).status_code == 204
    assert (await client.get(f"{MOD}/users/{user_id}", headers=mod(setup))).json()["notes"] == []


@pytest.mark.anyio
async def test_users_notes_and_reasons_stay_inside_their_community(client, session):
    ours = await create_community_setup(session)
    theirs = await create_community_setup(
        session,
        name="Other",
        slug="other",
        public_key="tfspub_other",
        origin="https://other.example",
        issuer="other-site",
        secret="other-secret",
        owner_email="other@example.com",
    )
    comment = await post_comment(client, theirs)
    user_id = comment["community_user_id"]
    note = await client.post(f"{MOD}/users/{user_id}/notes", headers=mod(theirs), json={"body": "Theirs"})

    assert (await client.get(f"{MOD}/users/{user_id}", headers=mod(ours))).status_code == 404
    assert (await client.post(f"{MOD}/users/{user_id}/notes", headers=mod(ours), json={"body": "x"})).status_code == 404
    assert (await client.delete(f"{MOD}/notes/{note.json()['id']}", headers=mod(ours))).status_code == 404
    assert (await client.get(f"{MOD}/users", params={"q": "alice"}, headers=mod(ours))).json()["total"] == 0

    res = await client.post(
        f"{MOD}/comments/batch", headers=mod(ours), json={"action": "hide", "comment_ids": [comment["id"]]}
    )
    assert res.json() == {"matched": 0, "changed": 0}

    await client.put(f"{MOD}/reasons", headers=admin(ours), json={"reasons": [{"key": "a", "label": "A"}]})
    keys = [r["key"] for r in (await client.get(f"{API}/config", headers=headers(theirs))).json()["report_reasons"]]
    assert "a" not in keys


@pytest.mark.anyio
async def test_comments_can_be_sorted_by_downvotes(client, session):
    setup = await create_community_setup(session)
    disliked = await post_comment(client, setup, content="Disliked")
    liked = await post_comment(client, setup, content="Liked")
    newest = await post_comment(client, setup, content="No votes")

    for subject in ("bob", "carol"):
        await client.post(f"{API}/comments/{disliked['id']}/votes", headers=headers(setup, subject), json={"value": -1})
    await client.post(f"{API}/comments/{liked['id']}/votes", headers=headers(setup, "bob"), json={"value": 1})

    res = await client.get(f"{MOD}/comments", params={"sort": "most_downvoted"}, headers=mod(setup))
    items = res.json()["items"]
    assert [item["id"] for item in items] == [disliked["id"], newest["id"], liked["id"]]
    assert items[0]["downvote_count"] == 2
    assert items[2]["upvote_count"] == 1


@pytest.mark.anyio
async def test_removed_comments_show_who_removed_them_and_why(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Bad")
    await client.post(
        f"{MOD}/comments/{comment['id']}/hide", headers=mod(setup), json={"reason_key": "spam", "note": "Again"}
    )

    (item,) = (await client.get(f"{MOD}/comments", params={"status": "hidden"}, headers=mod(setup))).json()["items"]
    assert item["removal"]["moderator"]["external_user_id"] == "mod"
    assert item["removal"]["reason"] == "Spam: Again"

    # Not for readers, and the latest removal is the one that counts
    assert "removal" not in (await thread_items(client, setup, "alice"))[0]

    await client.post(f"{MOD}/comments/{comment['id']}/restore", headers=mod(setup), json={})
    await client.post(f"{MOD}/comments/{comment['id']}/hide", headers=admin(setup), json={})
    (item,) = (await client.get(f"{MOD}/comments", params={"status": "hidden"}, headers=mod(setup))).json()["items"]
    assert item["removal"]["moderator"]["external_user_id"] == "boss"
    assert item["removal"]["reason"] is None

    restored = await client.post(f"{MOD}/comments/{comment['id']}/restore", headers=mod(setup), json={})
    assert restored.json()["removal"] is None


@pytest.mark.anyio
async def test_removed_comments_filter_by_reason_and_moderator(client, session):
    setup = await create_community_setup(session)
    spam = await post_comment(client, setup, content="Spam one")
    hate = await post_comment(client, setup, content="Hate one")
    await client.post(f"{MOD}/comments/{spam['id']}/hide", headers=mod(setup), json={"reason_key": "spam"})
    await client.post(f"{MOD}/comments/{hate['id']}/hide", headers=admin(setup), json={"reason_key": "hate"})
    moderator_id = (await client.get(f"{API}/me", headers=mod(setup))).json()["community_user_id"]

    async def removed(**params):
        res = await client.get(f"{MOD}/comments", params={"status": "hidden", **params}, headers=mod(setup))
        return [item["id"] for item in res.json()["items"]]

    assert await removed(removal_reason="Hate speech") == [hate["id"]]
    assert await removed(removed_by=moderator_id) == [spam["id"]]

    # One moderator's removals can be undone together, leaving the rest
    res = await client.post(
        f"{MOD}/comments/batch", headers=mod(setup), json={"action": "restore", "removed_by": moderator_id}
    )
    assert res.json() == {"matched": 1, "changed": 1}
    assert await removed() == [hate["id"]]


@pytest.mark.anyio
async def test_closed_reports_list_separately_and_say_who_decided(client, session):
    setup = await create_community_setup(session)
    removed = await post_comment(client, setup, content="Removed")
    dismissed = await post_comment(client, setup, content="Dismissed")
    still_open = await post_comment(client, setup, content="Open")
    for comment in (removed, dismissed, still_open):
        await report(client, setup, comment["id"])

    await hide(client, setup, removed["id"])
    await client.post(
        f"{MOD}/comments/{dismissed['id']}/reports/resolve", headers=mod(setup), json={"status": "dismissed"}
    )

    async def queue(**params):
        res = await client.get(f"{MOD}/reports", params=params, headers=mod(setup))
        assert res.status_code == 200, res.text
        return res.json()

    assert [entry["comment"]["id"] for entry in (await queue())["items"]] == [still_open["id"]]

    closed = await queue(status="closed")
    assert closed["total"] == 2
    outcomes = {entry["comment"]["content"]: entry["reports"][0] for entry in closed["items"]}
    assert outcomes["Removed"]["status"] == "resolved"
    assert outcomes["Dismissed"]["status"] == "dismissed"
    assert outcomes["Dismissed"]["resolver"]["external_user_id"] == "mod"

    res = await client.get(f"{MOD}/reports", params={"status": "nope"}, headers=mod(setup))
    assert res.status_code == 422


@pytest.mark.anyio
async def test_comments_removed_without_a_reason_can_be_found(client, session):
    setup = await create_community_setup(session)
    with_reason = await post_comment(client, setup, content="With")
    without = await post_comment(client, setup, content="Without")
    await hide(client, setup, with_reason["id"])
    await client.post(f"{MOD}/comments/{without['id']}/hide", headers=mod(setup), json={})

    res = await client.get(
        f"{MOD}/comments", params={"status": "hidden", "without_removal_reason": True}, headers=mod(setup)
    )
    assert [item["id"] for item in res.json()["items"]] == [without["id"]]

    res = await client.post(
        f"{MOD}/comments/batch", headers=mod(setup), json={"action": "restore", "without_removal_reason": True}
    )
    assert res.json() == {"matched": 1, "changed": 1}


@pytest.mark.anyio
async def test_the_log_says_what_each_action_was_about(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Offending text")
    await hide(client, setup, comment["id"])
    await client.post(
        f"{MOD}/bans", headers=mod(setup), json={"community_user_id": comment["community_user_id"]}
    )
    await client.post(f"{MOD}/threads/lock", headers=mod(setup), json={"thread_id": "anime:1", "locked": True})

    items = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    entries = {entry["action"]: entry for entry in items}

    assert entries["hide_comment"]["comment"]["content"] == "Offending text"
    assert entries["hide_comment"]["thread"]["unique_id"] == "anime:1"
    assert entries["lock_thread"]["comment"] is None
    assert entries["lock_thread"]["thread"]["unique_id"] == "anime:1"
    assert entries["ban_user"]["comment"] is None
    assert entries["ban_user"]["thread"] is None


@pytest.mark.anyio
async def test_users_filter_and_sort_by_their_record(client, session):
    setup = await create_community_setup(session)
    alice = await post_comment(client, setup, content="One")
    await post_comment(client, setup, content="Two")
    bob = await post_comment(client, setup, "bob", content="Three")
    carol = await post_comment(client, setup, "carol", content="Four")
    await hide(client, setup, bob["id"])
    await report(client, setup, carol["id"], "bob")
    await report(client, setup, carol["id"], "alice")
    await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": alice["community_user_id"]})

    async def names(**params):
        res = await client.get(f"{MOD}/users", params=params, headers=mod(setup))
        assert res.status_code == 200, res.text
        return [user["external_user_id"] for user in res.json()["items"]]

    assert await names(only="banned") == ["alice"]
    assert await names(only="removed") == ["bob"]
    assert await names(only="reported") == ["carol"]
    assert (await names(sort="most_comments"))[0] == "alice"
    assert (await names(sort="most_removed"))[0] == "bob"
    assert (await names(sort="most_reported"))[0] == "carol"


@pytest.mark.anyio
async def test_bans_filter_by_status_length_and_user(client, session):
    setup = await create_community_setup(session)
    ids = {}
    for name in ("alice", "bob", "carol"):
        ids[name] = (await post_comment(client, setup, name))["community_user_id"]
    soon = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": ids["alice"]})
    temporary = await client.post(
        f"{MOD}/bans", headers=admin(setup), json={"community_user_id": ids["bob"], "expires_at": soon}
    )
    lifted = await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": ids["carol"]})
    await client.post(f"{MOD}/bans/{lifted.json()['id']}/lift", headers=admin(setup), json={})

    expired = await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": ids["carol"], "expires_at": soon})
    row = await session.get(CommunityBan, expired.json()["id"])
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await session.commit()

    async def bans(**params):
        res = await client.get(f"{MOD}/bans", params=params, headers=mod(setup))
        assert res.status_code == 200, res.text
        return res.json()["items"]

    def users(items):
        return [item["community_user"]["external_user_id"] for item in items]

    assert sorted(users(await bans())) == ["alice", "bob"]
    assert users(await bans(status="expired")) == ["carol"]
    assert users(await bans(status="lifted")) == ["carol"]
    assert len(await bans(status="all")) == 4
    assert users(await bans(length="permanent")) == ["alice"]
    assert users(await bans(length="temporary")) == ["bob"]
    assert users(await bans(q="ali")) == ["alice"]
    assert users(await bans(sort="ending_soon")) == ["bob", "alice"]

    moderator_id = (await client.get(f"{API}/me", headers=admin(setup))).json()["community_user_id"]
    assert users(await bans(banned_by=moderator_id)) == ["bob"]
    assert temporary.json()["banned_by"]["external_user_id"] == "boss"
    assert (await bans(status="lifted"))[0]["lifted_by"]["external_user_id"] == "boss"


@pytest.mark.anyio
async def test_the_log_filters_by_action_people_and_date(client, session):
    setup = await create_community_setup(session)
    first = await post_comment(client, setup, content="One")
    second = await post_comment(client, setup, "bob", content="Two")
    await hide(client, setup, first["id"])
    await client.post(f"{MOD}/comments/{second['id']}/hide", headers=admin(setup), json={})
    await client.post(f"{MOD}/bans", headers=mod(setup), json={"community_user_id": first["community_user_id"]})
    moderator_id = (await client.get(f"{API}/me", headers=mod(setup))).json()["community_user_id"]

    async def log(**params):
        res = await client.get(f"{MOD}/actions", params=params, headers=mod(setup))
        assert res.status_code == 200, res.text
        return res.json()["items"]

    assert len(await log()) == 3
    assert len(await log(action="hide_comment")) == 2
    assert len(await log(moderator=moderator_id)) == 2
    assert len(await log(target=first["community_user_id"])) == 2
    assert len(await log(target=first["community_user_id"], action="ban_user")) == 1

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert await log(since=tomorrow) == []
    assert len(await log(until=tomorrow)) == 3


@pytest.mark.anyio
async def test_dismissing_is_logged_and_reports_can_be_reopened(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, content="Borderline")
    await report(client, setup, comment["id"])
    resolve = f"{MOD}/comments/{comment['id']}/reports/resolve"

    await client.post(resolve, headers=mod(setup), json={"status": "dismissed"})
    (entry,) = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    assert entry["action"] == "dismiss_reports"
    assert entry["target"]["external_user_id"] == "alice"

    # Nothing open: nothing to dismiss, and nothing to log
    await client.post(resolve, headers=mod(setup), json={"status": "dismissed"})
    assert (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["total"] == 1

    res = await client.post(f"{MOD}/comments/{comment['id']}/reports/reopen", headers=mod(setup))
    assert res.status_code == 204
    (item,) = (await client.get(f"{MOD}/reports", headers=mod(setup))).json()["items"]
    assert item["reports"][0]["resolver"] is None
    assert (await client.get(f"{MOD}/actions", params={"action": "reopen_reports"}, headers=mod(setup))).json()["total"] == 1

    await hide(client, setup, comment["id"])
    res = await client.post(f"{MOD}/comments/{comment['id']}/reports/reopen", headers=mod(setup))
    assert res.status_code == 409


@pytest.mark.anyio
async def test_other_needs_a_description(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    url = f"{API}/comments/{comment['id']}/reports"
    bob = headers(setup, "bob")

    assert (await client.post(url, headers=bob, json={"reason": "other"})).status_code == 422
    assert (await client.post(url, headers=bob, json={"reason": "other", "details": "   "})).status_code == 422

    sent = await client.post(url, headers=bob, json={"reason": "other", "details": " Posted in the wrong place "})
    assert sent.status_code == 204

    items = (await client.get(f"{MOD}/reports", headers=mod(setup))).json()["items"]
    assert items[0]["reports"][0]["details"] == "Posted in the wrong place"


@pytest.mark.anyio
async def test_a_report_description_is_kept_short(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    url = f"{API}/comments/{comment['id']}/reports"
    bob = headers(setup, "bob")

    assert (await client.post(url, headers=bob, json={"reason": "other", "details": "x" * 101})).status_code == 422
    assert (await client.post(url, headers=bob, json={"reason": "other", "details": "x" * 100})).status_code == 204


@pytest.mark.anyio
async def test_removing_for_other_tells_the_author_why(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup)
    url = f"{MOD}/comments/{comment['id']}/hide"

    assert (await client.post(url, headers=mod(setup), json={"reason_key": "other"})).status_code == 422
    blank = await client.post(url, headers=mod(setup), json={"reason_key": "other", "reason_detail": "  "})
    assert blank.status_code == 422
    long = await client.post(url, headers=mod(setup), json={"reason_key": "other", "reason_detail": "x" * 201})
    assert long.status_code == 422

    payload = {"reason_key": "other", "reason_detail": " Spoils the finale ", "note": "Private"}
    assert (await client.post(url, headers=mod(setup), json=payload)).status_code == 200

    (own,) = await thread_items(client, setup, "alice")
    assert (own["removal_reason"], own["removal_detail"]) == ("Other", "Spoils the finale")
    mine = (await client.get(f"{API}/comments/mine", headers=headers(setup, "alice"))).json()
    assert mine["items"][0]["removal_detail"] == "Spoils the finale"
    (other,) = await thread_items(client, setup, "bob")
    assert other["removal_detail"] is None

    # It stays under Other for moderators, however it was worded
    found = await client.get(f"{MOD}/comments", headers=mod(setup), params={"status": "hidden", "removal_reason": "Other"})
    assert [item["id"] for item in found.json()["items"]] == [comment["id"]]
    (entry,) = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    assert entry["reason"] == "Other: Spoils the finale: Private"

    await client.post(f"{MOD}/comments/{comment['id']}/restore", headers=mod(setup), json={})
    (restored,) = await thread_items(client, setup, "alice")
    assert restored["removal_detail"] is None


@pytest.mark.anyio
async def test_only_other_takes_a_detail_and_a_batch_needs_one(client, session):
    setup = await create_community_setup(session)
    first = await post_comment(client, setup)
    second = await post_comment(client, setup, content="Second")

    spam = {"reason_key": "spam", "reason_detail": "Ignored"}
    assert (await client.post(f"{MOD}/comments/{first['id']}/hide", headers=mod(setup), json=spam)).status_code == 200

    batch = {"action": "hide", "comment_ids": [int(second["id"])], "reason_key": "other"}
    assert (await client.post(f"{MOD}/comments/batch", headers=mod(setup), json=batch)).status_code == 422
    done = await client.post(f"{MOD}/comments/batch", headers=mod(setup), json={**batch, "reason_detail": "Off the rails"})
    assert done.json()["changed"] == 1

    details = {item["id"]: item["removal_detail"] for item in await thread_items(client, setup, "alice")}
    assert details == {first["id"]: None, second["id"]: "Off the rails"}


async def user_id(client, setup, subject, role=None):
    """Visiting is what records their role."""
    me = await client.get(f"{API}/me", headers=headers(setup, subject, role=role))
    return me.json()["community_user_id"]


async def ban(client, setup, by, target):
    return await client.post(f"{MOD}/bans", headers=by, json={"community_user_id": target})


@pytest.mark.anyio
async def test_who_can_ban_whom(client, session):
    setup = await create_community_setup(session)
    user = await user_id(client, setup, "alice")
    moderator = await user_id(client, setup, "mod", role="moderator")
    other_moderator = await user_id(client, setup, "mod2", role="moderator")
    boss = await user_id(client, setup, "boss", role="admin")
    other_boss = await user_id(client, setup, "boss2", role="admin")

    for by, target, detail in [
        (mod(setup), moderator, "You can't ban yourself"),
        (admin(setup), boss, "You can't ban yourself"),
        (mod(setup), other_moderator, "Only admins can ban moderators"),
        (mod(setup), boss, "Admins can't be banned"),
        (admin(setup), other_boss, "Admins can't be banned"),
    ]:
        refused = await ban(client, setup, by, target)
        assert refused.status_code == 403
        assert refused.json()["detail"] == detail

    assert (await ban(client, setup, mod(setup), user)).status_code == 200
    assert (await ban(client, setup, admin(setup), other_moderator)).status_code == 200


@pytest.mark.anyio
async def test_remove_and_ban_follows_the_same_rules(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "mod", role="moderator")
    comment = await post_comment(client, setup, subject="boss")
    await user_id(client, setup, "boss", role="admin")

    url = f"{MOD}/comments/{comment['id']}/hide"
    refused = await client.post(url, headers=mod(setup), json={"ban": True})
    assert refused.status_code == 403
    assert (await thread_items(client, setup, "boss"))[0]["status"] == "visible"

    assert (await client.post(url, headers=mod(setup), json={})).status_code == 200


@pytest.mark.anyio
async def test_a_banned_moderator_loses_moderation_until_an_admin_lifts_it(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "alice")
    moderator = await user_id(client, setup, "mod", role="moderator")
    await user_id(client, setup, "mod2", role="moderator")
    await user_id(client, setup, "boss", role="admin")

    banned = await ban(client, setup, admin(setup), moderator)
    assert banned.status_code == 200
    lift = f"{MOD}/bans/{banned.json()['id']}/lift"

    assert (await client.get(f"{API}/me", headers=mod(setup))).json()["staff_role"] is None
    assert (await client.get(f"{MOD}/reports", headers=mod(setup))).status_code == 403
    assert (await client.post(lift, headers=mod(setup), json={})).status_code == 403

    colleague = headers(setup, "mod2", role="moderator")
    refused = await client.post(lift, headers=colleague, json={})
    assert refused.status_code == 403
    assert refused.json()["detail"] == "Only admins can lift a moderator's ban"

    assert (await client.post(lift, headers=admin(setup), json={})).status_code == 200
    assert (await client.get(f"{API}/me", headers=mod(setup))).json()["staff_role"] == "moderator"
    assert (await client.get(f"{MOD}/reports", headers=mod(setup))).status_code == 200


@pytest.mark.anyio
async def test_losing_a_role_ends_the_protection(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "mod", role="moderator")
    former = await user_id(client, setup, "mod2", role="moderator")
    assert (await ban(client, setup, mod(setup), former)).status_code == 403

    assert await user_id(client, setup, "mod2") == former
    assert (await ban(client, setup, mod(setup), former)).status_code == 200


@pytest.mark.anyio
async def test_a_token_with_an_unknown_role_keeps_the_recorded_one(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "mod", role="moderator")
    other = await user_id(client, setup, "mod2", role="moderator")

    # mod2 visits through an embed whose tokens don't say their role, even one claiming a role
    unknown = create_test_token(
        secret=setup["secret"],
        issuer=setup["issuer"],
        subject="mod2",
        username="mod2",
        role="admin",
        claims={"threadfs_role_unknown": True},
    )
    by_embed = embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=unknown)
    me = (await client.get(f"{API}/me", headers=by_embed)).json()
    assert me["community_user_id"] == other
    assert me["staff_role"] is None

    # It acts as a regular user there, and is still protected and listed as staff
    assert (await client.get(f"{MOD}/reports", headers=by_embed)).status_code == 403
    assert (await ban(client, setup, mod(setup), other)).status_code == 403
    users = (await client.get(f"{MOD}/users", headers=mod(setup))).json()["items"]
    assert {user["external_user_id"]: user["last_staff_role"] for user in users}["mod2"] == "moderator"


@pytest.mark.anyio
async def test_moderators_see_who_is_staff(client, session):
    setup = await create_community_setup(session)
    comment = await post_comment(client, setup, subject="mod2")
    await user_id(client, setup, "mod2", role="moderator")
    await user_id(client, setup, "mod", role="moderator")

    users = (await client.get(f"{MOD}/users", headers=mod(setup))).json()["items"]
    assert {user["external_user_id"]: user["last_staff_role"] for user in users}["mod2"] == "moderator"

    listed = (await client.get(f"{MOD}/comments", headers=mod(setup))).json()["items"]
    assert listed[0]["id"] == comment["id"]
    assert listed[0]["community_user"]["last_staff_role"] == "moderator"

    (public,) = await thread_items(client, setup, "alice")
    assert "last_staff_role" not in public["community_user"]


async def comments(client, setup, count, subject="alice", source="bad.example"):
    return [await post_comment(client, setup, subject=subject, content=f"Comment {n}", source=source) for n in range(count)]


def batch(http, by, **body):
    return http.post(f"{MOD}/comments/batch", headers=by, json=body)


async def small_limits(client, setup):
    await user_id(client, setup, "boss", role="admin")
    res = await client.put(
        f"{MOD}/admin/limits", headers=admin(setup), json={"max_batch_size": 3, "max_daily_batch_changes": 5}
    )
    assert res.status_code == 200, res.text


@pytest.mark.anyio
async def test_a_moderator_can_only_change_so_many_comments_at_once(client, session):
    setup = await create_community_setup(session)
    await small_limits(client, setup)
    await comments(client, setup, 4)
    await user_id(client, setup, "mod", role="moderator")
    await user_id(client, setup, "boss", role="admin")
    wide = {"action": "hide", "source": "bad.example"}

    preview = await batch(client, mod(setup), **wide, dry_run=True)
    assert preview.json()["matched"] == 4
    assert "up to 3 at once" in preview.json()["refused"]

    refused = await batch(client, mod(setup), **wide)
    assert refused.status_code == 403
    assert len([c for c in await thread_items(client, setup, "bob", thread="anime:1") if c["status"] == "visible"]) == 4

    assert (await batch(client, admin(setup), **wide)).json()["changed"] == 4

    restore = await batch(client, mod(setup), action="restore", source="bad.example")
    assert restore.status_code == 403


@pytest.mark.anyio
async def test_a_moderator_can_only_change_so_many_comments_a_day(client, session):
    setup = await create_community_setup(session)
    await small_limits(client, setup)
    first, second, third = [
        await comments(client, setup, 3, subject=f"user{n}", source=f"site{n}.example") for n in range(3)
    ]
    await user_id(client, setup, "mod", role="moderator")

    assert (await batch(client, mod(setup), action="hide", source="site0.example")).status_code == 200
    preview = await batch(client, mod(setup), action="hide", source="site1.example", dry_run=True)
    assert "You have 2 left" in preview.json()["refused"]
    assert (await batch(client, mod(setup), action="hide", source="site1.example")).status_code == 403

    two = {"action": "hide", "comment_ids": [int(c["id"]) for c in second[:2]]}
    assert (await batch(client, mod(setup), **two)).status_code == 200
    one = {"action": "hide", "comment_ids": [int(third[0]["id"])]}
    assert (await batch(client, mod(setup), **one)).status_code == 403

    # Each moderator has their own allowance
    other = headers(setup, "mod2", role="moderator")
    await client.get(f"{API}/me", headers=other)
    assert (await batch(client, other, **one)).status_code == 200


@pytest.mark.anyio
async def test_clearing_out_one_regular_user_isnt_limited(client, session):
    setup = await create_community_setup(session)
    await small_limits(client, setup)
    await comments(client, setup, 4, subject="spammer", source="spam.example")
    await comments(client, setup, 4, subject="mod2", source="staff.example")
    spammer = await user_id(client, setup, "spammer")
    colleague = await user_id(client, setup, "mod2", role="moderator")
    await user_id(client, setup, "mod", role="moderator")

    cleared = await batch(client, mod(setup), action="hide", community_user_id=spammer)
    assert cleared.json()["changed"] == 4
    # It doesn't use up the daily allowance either
    preview = await batch(client, mod(setup), action="hide", source="staff.example", comment_ids=None, dry_run=True)
    assert "up to 3 at once" in preview.json()["refused"]

    refused = await batch(client, mod(setup), action="hide", community_user_id=colleague)
    assert refused.status_code == 403
    restored = await batch(client, mod(setup), action="restore", community_user_id=spammer)
    assert restored.status_code == 403


@pytest.mark.anyio
async def test_a_batch_is_one_line_in_the_log_unless_its_about_one_user(client, session):
    setup = await create_community_setup(session)
    await comments(client, setup, 3)
    alice = await user_id(client, setup, "alice")
    await batch(client, mod(setup), action="hide", source="bad.example", reason_key="spam")

    (entry,) = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    assert entry["action"] == "hide_batch"
    assert entry["reason"] == "Spam"
    assert entry["batch"]["comment_count"] == 3
    assert entry["batch"]["undone_at"] is None

    found = await client.get(f"{MOD}/actions", headers=mod(setup), params={"action": "hide_comment"})
    assert [item["action"] for item in found.json()["items"]] == ["hide_batch"]

    theirs = await client.get(f"{MOD}/actions", headers=mod(setup), params={"target": alice})
    assert {item["action"] for item in theirs.json()["items"]} == {"hide_comment"}
    assert len(theirs.json()["items"]) == 3


async def logged_batch(client, setup, action):
    items = (await client.get(f"{MOD}/actions", headers=mod(setup), params={"action": action})).json()["items"]
    return next(item["batch"]["id"] for item in items if item["batch"])


@pytest.mark.anyio
async def test_an_admin_can_undo_a_removal_batch(client, session):
    setup = await create_community_setup(session)
    first, second = await comments(client, setup, 2)
    await user_id(client, setup, "boss", role="admin")
    await client.post(f"{MOD}/comments/{first['id']}/hide", headers=mod(setup), json={"reason_key": "hate"})
    await batch(client, mod(setup), action="hide", source="bad.example", reason_key="spam")

    batch_id = await logged_batch(client, setup, "hide_comment")
    url = f"{MOD}/batches/{batch_id}/undo"
    assert (await client.post(url, headers=mod(setup))).status_code == 403

    undone = await client.post(url, headers=admin(setup))
    assert undone.json() == {"changed": 1, "skipped": 0}

    # Only what the batch did: the comment removed before it stays removed
    statuses = {c["id"]: (c["status"], c["removal_reason"]) for c in await thread_items(client, setup, "alice")}
    assert statuses == {first["id"]: ("hidden", "Hate speech"), second["id"]: ("visible", None)}

    assert (await client.post(url, headers=admin(setup))).status_code == 409
    log = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    assert log[0]["action"] == "undo_batch"
    assert next(e for e in log if e["action"] == "hide_batch")["batch"]["undone_at"]


@pytest.mark.anyio
async def test_undoing_a_restore_batch_puts_the_reasons_back(client, session):
    setup = await create_community_setup(session)
    first, second = await comments(client, setup, 2)
    await user_id(client, setup, "boss", role="admin")
    other = {"reason_key": "other", "reason_detail": "Spoils the ending"}
    await client.post(f"{MOD}/comments/{first['id']}/hide", headers=mod(setup), json={"reason_key": "hate"})
    await client.post(f"{MOD}/comments/{second['id']}/hide", headers=mod(setup), json=other)

    await batch(client, mod(setup), action="restore", source="bad.example")
    assert {c["status"] for c in await thread_items(client, setup, "alice")} == {"visible"}

    batch_id = await logged_batch(client, setup, "restore_comment")
    assert (await client.post(f"{MOD}/batches/{batch_id}/undo", headers=admin(setup))).json()["changed"] == 2

    items = {c["id"]: c for c in await thread_items(client, setup, "alice")}
    assert items[first["id"]]["removal_reason"] == "Hate speech"
    assert (items[second["id"]]["removal_reason"], items[second["id"]]["removal_detail"]) == ("Other", "Spoils the ending")
    assert items[first["id"]]["status"] == items[second["id"]]["status"] == "hidden"


@pytest.mark.anyio
async def test_undo_leaves_comments_that_changed_after_the_batch(client, session):
    setup = await create_community_setup(session)
    first, second, third = await comments(client, setup, 3)
    await user_id(client, setup, "boss", role="admin")
    await batch(client, mod(setup), action="hide", source="bad.example")

    # Put back by hand and removed again for its own reason, and deleted-while-restored by its author
    await client.post(f"{MOD}/comments/{first['id']}/restore", headers=mod(setup), json={})
    await client.post(f"{MOD}/comments/{first['id']}/hide", headers=mod(setup), json={"reason_key": "hate"})
    await client.post(f"{MOD}/comments/{second['id']}/restore", headers=mod(setup), json={})
    await client.delete(f"{API}/comments/{second['id']}", headers=headers(setup, "alice"))

    batch_id = await logged_batch(client, setup, "hide_comment")
    undone = await client.post(f"{MOD}/batches/{batch_id}/undo", headers=admin(setup))
    assert undone.json() == {"changed": 1, "skipped": 2}

    items = {c["id"]: c for c in await thread_items(client, setup, "alice")}
    assert (items[first["id"]]["status"], items[first["id"]]["removal_reason"]) == ("hidden", "Hate speech")
    assert items[second["id"]]["status"] == "deleted"
    assert items[third["id"]]["status"] == "visible"


@pytest.mark.anyio
async def test_a_batch_stays_inside_its_community(client, session):
    setup = await create_community_setup(session)
    await comments(client, setup, 1)
    await batch(client, mod(setup), action="hide", source="bad.example")
    batch_id = await logged_batch(client, setup, "hide_comment")

    other = await create_community_setup(
        session,
        name="Other",
        slug="other",
        public_key="tfspub_other",
        origin="https://other.example",
        issuer="other-site",
        secret="other-secret",
        owner_email="other@example.com",
    )
    await session.commit()
    assert (await client.post(f"{MOD}/batches/{batch_id}/undo", headers=admin(other))).status_code == 404


@pytest.mark.anyio
async def test_only_admins_reach_the_admin_panel(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "mod", role="moderator")
    limits = {"max_batch_size": 10, "max_daily_batch_changes": 20}

    assert (await client.get(f"{MOD}/admin", headers=mod(setup))).status_code == 403
    assert (await client.put(f"{MOD}/admin/limits", headers=mod(setup), json=limits)).status_code == 403
    assert (await client.get(f"{MOD}/admin", headers=admin(setup))).status_code == 200


@pytest.mark.anyio
async def test_the_overview_shows_staff_activity_and_origins(client, session):
    setup = await create_community_setup(session)
    first, second, third = await comments(client, setup, 3)
    await user_id(client, setup, "boss", role="admin")
    moderator = await user_id(client, setup, "mod", role="moderator")
    idle = await user_id(client, setup, "mod2", role="moderator")
    alice = await user_id(client, setup, "alice")

    await client.post(f"{MOD}/comments/{first['id']}/hide", headers=mod(setup), json={})
    await batch(client, mod(setup), action="hide", comment_ids=[int(second["id"]), int(third["id"])])
    await ban(client, setup, mod(setup), alice)
    await ban(client, setup, admin(setup), idle)

    overview = (await client.get(f"{MOD}/admin", headers=admin(setup))).json()
    assert overview["origins"] == [setup["origin"]]
    assert (overview["max_batch_size"], overview["max_daily_batch_changes"]) == (50, 200)

    staff = {row["user"]["id"]: row for row in overview["staff"]}
    assert alice not in staff
    assert {row["user"]["external_user_id"] for row in overview["staff"]} == {"boss", "mod", "mod2"}
    row = staff[moderator]
    assert (row["removed"], row["bans"], row["batches"], row["is_suspended"]) == (3, 1, 1, False)
    assert row["last_active_at"]
    assert staff[idle]["is_suspended"] is True
    assert staff[idle]["last_active_at"] is None

    # Secrets never leave the server
    assert setup["secret"] not in str(overview)


@pytest.mark.anyio
async def test_limits_are_validated_logged_and_per_community(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "boss", role="admin")
    url = f"{MOD}/admin/limits"

    for bad in [
        {"max_batch_size": 0, "max_daily_batch_changes": 10},
        {"max_batch_size": 20, "max_daily_batch_changes": 10},
        {"max_batch_size": 5000, "max_daily_batch_changes": 6000},
    ]:
        assert (await client.put(url, headers=admin(setup), json=bad)).status_code == 422

    saved = await client.put(url, headers=admin(setup), json={"max_batch_size": 10, "max_daily_batch_changes": 40})
    assert saved.json()["max_batch_size"] == 10

    (entry,) = (await client.get(f"{MOD}/actions", headers=admin(setup))).json()["items"]
    assert entry["action"] == "update_limits"
    assert entry["reason"] == "50 at once, 200 a day → 10 at once, 40 a day"

    # Saving the same values again isn't a change
    await client.put(url, headers=admin(setup), json={"max_batch_size": 10, "max_daily_batch_changes": 40})
    assert (await client.get(f"{MOD}/actions", headers=admin(setup))).json()["total"] == 1

    other = await create_community_setup(
        session,
        name="Other",
        slug="other",
        public_key="tfspub_other",
        origin="https://other.example",
        issuer="other-site",
        secret="other-secret",
        owner_email="other@example.com",
    )
    await session.commit()
    assert (await client.get(f"{MOD}/admin", headers=admin(other))).json()["max_batch_size"] == 50


@pytest.mark.anyio
async def test_moderators_can_clear_images_the_host_took_down(client, session):
    setup = await create_community_setup(session)
    images = {"avatar_url": "https://example.com/a.png", "avatar_frame_url": "https://example.com/f.webp"}
    def as_alice(**token_args):
        token = create_test_token(secret=setup["secret"], issuer=setup["issuer"], subject="alice", username="alice", **token_args)
        return embed_headers(public_key=setup["public_key"], origin=setup["origin"], token=token)

    await client.get(f"{API}/me", headers=as_alice(avatar_url=images["avatar_url"], claims={"avatar_frame_url": images["avatar_frame_url"]}))

    async def stored():
        # A token without image claims leaves them as they are
        res = await client.get(f"{API}/me", headers=as_alice(omit_avatar=True))
        return res.json()["avatar_url"], res.json()["avatar_frame_url"]

    clear = lambda by, **body: client.post(f"{MOD}/users/clear-images", headers=by, json={"external_user_id": "alice", **body})

    assert (await clear(headers(setup, "bob"), frame=True)).status_code == 403
    assert await stored() == (images["avatar_url"], images["avatar_frame_url"])

    assert (await clear(mod(setup), frame=True, reason="Copied artwork")).status_code == 204
    assert await stored() == (images["avatar_url"], None)
    assert (await clear(mod(setup), avatar=True)).status_code == 204
    assert await stored() == (None, None)

    # Clearing what's already gone, or someone who never came, changes and logs nothing more
    assert (await clear(mod(setup), avatar=True, frame=True)).status_code == 204
    res = await client.post(f"{MOD}/users/clear-images", headers=mod(setup), json={"external_user_id": "nobody", "avatar": True})
    assert res.status_code == 204

    log = (await client.get(f"{MOD}/actions", headers=mod(setup))).json()["items"]
    assert [(entry["action"], entry["reason"]) for entry in log] == [("clear_avatar", None), ("clear_avatar_frame", "Copied artwork")]
    assert log[0]["target"]["external_user_id"] == "alice"

    # The host stays the source: its next token sets them again
    await client.get(f"{API}/me", headers=as_alice(avatar_url=images["avatar_url"], claims={"avatar_frame_url": images["avatar_frame_url"]}))
    assert await stored() == (images["avatar_url"], images["avatar_frame_url"])


@pytest.mark.anyio
async def test_admins_set_the_rules_link_that_the_widget_gets(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "boss", role="admin")
    await user_id(client, setup, "mod", role="moderator")
    url = f"{MOD}/admin/rules"
    config = lambda: client.get(  # noqa: E731
        "/api/v1/embed/config",
        headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"]),
    )

    assert (await config()).json()["rules_url"] is None
    assert (await client.put(url, headers=mod(setup), json={"rules_url": "https://example.com/rules"})).status_code == 403
    assert (await client.put(url, headers=admin(setup), json={"rules_url": "javascript:alert(1)"})).status_code == 422

    saved = await client.put(url, headers=admin(setup), json={"rules_url": " https://example.com/rules "})
    assert saved.status_code == 200
    assert saved.json()["rules_url"] == "https://example.com/rules"
    assert (await config()).json()["rules_url"] == "https://example.com/rules"

    (entry,) = (await client.get(f"{MOD}/actions", headers=admin(setup))).json()["items"]
    assert entry["action"] == "update_rules"
    assert entry["reason"] == "https://example.com/rules"

    # Empty clears it
    await client.put(url, headers=admin(setup), json={"rules_url": ""})
    assert (await config()).json()["rules_url"] is None


@pytest.mark.anyio
async def test_admins_turn_gifs_on_and_off_with_a_klipy_key(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "boss", role="admin")
    await user_id(client, setup, "mod", role="moderator")
    url = f"{MOD}/admin/gifs"
    config = lambda: client.get(  # noqa: E731
        "/api/v1/embed/config",
        headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"]),
    )

    assert (await config()).json()["gifs"] is None
    assert (await client.put(url, headers=mod(setup), json={"klipy_app_key": "abc123"})).status_code == 403
    # It goes in KLIPY's URL path, so nothing that could change the path
    assert (await client.put(url, headers=admin(setup), json={"klipy_app_key": "../x"})).status_code == 422

    saved = await client.put(url, headers=admin(setup), json={"klipy_app_key": " abc_123-XYZ "})
    assert saved.status_code == 200
    assert saved.json()["klipy_app_key"] == "abc_123-XYZ"
    assert (await config()).json()["gifs"] == {"provider": "klipy", "app_key": "abc_123-XYZ"}

    await client.put(url, headers=admin(setup), json={"klipy_app_key": "other"})
    await client.put(url, headers=admin(setup), json={"klipy_app_key": ""})
    assert (await config()).json()["gifs"] is None

    # Logged without the key
    entries = (await client.get(f"{MOD}/actions", headers=admin(setup))).json()["items"]
    assert [(e["action"], e["reason"]) for e in entries] == [
        ("update_gifs", "turned off"),
        ("update_gifs", "key changed"),
        ("update_gifs", "turned on"),
    ]


@pytest.mark.anyio
async def test_admins_choose_which_hosts_images_show_from(client, session):
    setup = await create_community_setup(session)
    await user_id(client, setup, "boss", role="admin")
    await user_id(client, setup, "mod", role="moderator")
    url = f"{MOD}/admin/image-hosts"
    config = lambda: client.get(  # noqa: E731
        "/api/v1/embed/config",
        headers=embed_headers(public_key=setup["public_key"], origin=setup["origin"]),
    )

    assert (await config()).json()["image_hosts"] == []
    assert (await client.put(url, headers=mod(setup), json={"image_hosts": ["i.imgur.com"]})).status_code == 403
    # Exact hostnames only: no scheme, path, port or wildcard
    for bad in ("https://i.imgur.com", "i.imgur.com/a", "*.imgur.com", "i.imgur.com:443", "localhost"):
        res = await client.put(url, headers=admin(setup), json={"image_hosts": [bad]})
        assert res.status_code == 422, bad

    saved = await client.put(url, headers=admin(setup), json={"image_hosts": [" I.Imgur.com ", "i.imgur.com", "", "cdn.example.org"]})
    assert saved.status_code == 200
    assert saved.json()["image_hosts"] == ["i.imgur.com", "cdn.example.org"]
    assert (await config()).json()["image_hosts"] == ["i.imgur.com", "cdn.example.org"]

    await client.put(url, headers=admin(setup), json={"image_hosts": ["i.imgur.com", "images.example.net"]})
    (entry, first) = (await client.get(f"{MOD}/actions", headers=admin(setup))).json()["items"]
    assert (entry["action"], entry["reason"]) == ("update_image_hosts", "added images.example.net; removed cdn.example.org")
    assert first["reason"] == "added i.imgur.com, cdn.example.org"
