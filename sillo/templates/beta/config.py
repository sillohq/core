from sillo.config import MakeConfig

app_config = MakeConfig(
    {
        "debug": True,
        "title": "{{project_name_title}}",
    },
)
