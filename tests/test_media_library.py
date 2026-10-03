from aitihasik_katha.services.media_library import LibraryItem, MediaLibrary, normalise_query


def _item(title="Linge Ping.jpg"):
    return LibraryItem(
        title=title, file="Linge_Ping.jpg", kind="image", license="CC BY 2.0",
        artist="Mithun Kunwar", page_url="https://commons.wikimedia.org/wiki/File:Linge_Ping.jpg",
        width=6000, height=4000,
    )


def test_an_added_item_is_found_again_for_the_same_search_in_a_new_session(tmp_path):
    library = MediaLibrary(tmp_path)
    path = library.file_path_for("Linge Ping.jpg")
    path.write_bytes(b"jpeg")
    library.add(_item(), "Linge Ping Dashain")

    reopened = MediaLibrary(tmp_path)

    found = reopened.for_query("  linge   PING dashain ")
    assert [i.title for i in found] == ["Linge Ping.jpg"]
    assert reopened.path_of(found[0]) == str(tmp_path / "files" / "Linge_Ping.jpg")


def test_the_credit_names_the_author_licence_and_source():
    assert _item().credit == '"Linge Ping.jpg" by Mithun Kunwar, CC BY 2.0, via Wikimedia Commons'


def test_a_file_that_was_deleted_is_not_offered(tmp_path):
    library = MediaLibrary(tmp_path)
    library.add(_item(), "linge ping")

    assert library.for_query("linge ping") == []
    assert library.get("Linge Ping.jpg") is None


def test_the_same_file_found_by_two_searches_is_stored_once_with_both_queries(tmp_path):
    library = MediaLibrary(tmp_path)
    library.file_path_for("Linge Ping.jpg").write_bytes(b"jpeg")
    library.add(_item(), "linge ping")
    library.add(_item(), "dashain swing")

    assert len(library._items) == 1
    assert library.for_query("dashain swing")[0].queries == ["linge ping", "dashain swing"]


def test_search_phrases_are_compared_ignoring_case_and_spacing():
    assert normalise_query("  Patan   Durbar SQUARE ") == "patan durbar square"
