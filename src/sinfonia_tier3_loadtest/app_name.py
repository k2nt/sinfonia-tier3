from uuid import UUID


APP_NAME_TO_UUID = {
    "helloworld": "00000000-0000-0000-0000-000000000000",
    "loadtest": "00000000-0000-0000-0000-000000000111",
    "loadtest-port30126": "00000000-0000-0000-0000-000000030126",
    "loadtest-port30127": "00000000-0000-0000-0000-000000030127",
    "loadtest-port30128": "00000000-0000-0000-0000-000000030128",
    "loadtest-port30139": "00000000-0000-0000-0000-000000030139",
    "loadtest-port30130": "00000000-0000-0000-0000-000000030130",
}

UUID_TO_APP_NAME = {
    "00000000-0000-0000-0000-000000000111": "loadtest",
    "00000000-0000-0000-0000-000000030126": "loadtest-port30126",
    "00000000-0000-0000-0000-000000030127": "loadtest-port30127",
    "00000000-0000-0000-0000-000000030128": "loadtest-port30128",
    "00000000-0000-0000-0000-000000030139": "loadtest-port30139",
    "00000000-0000-0000-0000-000000030130": "loadtest-port30130",
    "00000000-0000-0000-0000-000000000000": "helloworld",
}


def app_name_to_uuid(value: str) -> UUID:
    uuid = APP_NAME_TO_UUID.get(value, value)
    return UUID(uuid)


def uuid_to_app_name(uuid: str | UUID) -> str:
    return UUID_TO_APP_NAME[str(uuid)]
