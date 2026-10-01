from aitihasik_katha.services.instagram_service import InstagramService


class _Recorder(InstagramService):
    def __init__(self, replies):
        super().__init__("user-1", "token")
        self.posts = []
        self._replies = list(replies)

    def _post(self, url, params):
        self.posts.append(params)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def test_reel_with_a_cover_sends_cover_url_instead_of_a_frame_offset():
    service = _Recorder([{"id": "c1"}])

    assert service.create_media_container("https://v/x.mp4", "cap", "REELS", cover_url="https://v/cover.jpg") == "c1"

    params = service.posts[0]
    assert params["cover_url"] == "https://v/cover.jpg"
    assert "thumb_offset" not in params


def test_reel_without_a_cover_lets_instagram_pick_the_first_frame():
    service = _Recorder([{"id": "c1"}])

    service.create_media_container("https://v/x.mp4", "cap", "REELS")

    assert service.posts[0]["thumb_offset"] == 0
    assert "cover_url" not in service.posts[0]


def test_a_rejected_cover_is_retried_without_it(monkeypatch):
    service = _Recorder([RuntimeError("bad cover"), {"id": "c2"}, {"id": "published"}])
    monkeypatch.setattr(service, "is_media_ready", lambda container_id: True)

    service.upload_media("https://v/x.mp4", "cap", "REELS", cover_url="https://v/cover.jpg")

    assert "cover_url" in service.posts[0]
    assert "cover_url" not in service.posts[1]
    assert service.posts[2]["creation_id"] == "c2"
