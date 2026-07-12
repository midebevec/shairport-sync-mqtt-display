import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web_server import DisplayState, create_app, build_image_data_url
from volume import scaled_volume_percent


def test_volume_and_cover_helpers():
    assert scaled_volume_percent("-15.0,0,0,0") == 50
    assert scaled_volume_percent("-144.0,0,0,0") == 0

    image_url = build_image_data_url(b"\x89PNG\r\n\x1a\x00abc")
    assert image_url.startswith("data:image/png;base64,")


def test_state_serialization_handles_cover_bytes():
    state = DisplayState()
    state.update("cover_art", b"\x89PNG\r\n\x1a\x00abc")
    payload = state.get()

    assert payload["cover_image"].startswith("data:image/png;base64,")
    assert isinstance(payload["cover_art"], str)
    json.dumps(payload)


def test_navigation_and_page_layout(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"clock": {"enabled": True, "type": "analog"}}))

    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/details")
    assert response.status_code == 200
    assert b"Playback Details" in response.data
    assert b"/details" in response.data
    assert b"/clock" in response.data
    assert b"grid-template-columns" in response.data
    assert b'class="nav-link active"' in response.data
    assert b'<meta name="viewport"' in response.data
    assert b"@media (max-width: 700px)" in response.data

    response = client.get("/")
    assert response.status_code == 200
    assert b"Now Playing" in response.data
    assert b'id="volume-bar"' in response.data

    response = client.post(
        "/api/config",
        data={
            "clock.enabled": "false",
            "clock.type": "digital",
            "clock.time_window.start": "09:30",
            "clock.time_window.end": "19:45",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    updated_config = yaml.safe_load(config_path.read_text())
    assert updated_config["clock"]["enabled"] is False
    assert updated_config["clock"]["type"] == "digital"
    assert updated_config["clock"]["time_window"]["start"] == "09:30"
    assert updated_config["clock"]["time_window"]["end"] == "19:45"
