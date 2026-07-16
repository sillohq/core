from sillo.lifecycle import RequestContext


class TestRequestContext:
    def test_basic_context_usage(self):
        with RequestContext() as ctx:
            ctx["key"] = "value"
            assert ctx["key"] == "value"
            assert ctx.get("key") == "value"
            assert ctx.get("missing", "default") == "default"

    def test_context_isolation(self):
        with RequestContext() as ctx1:
            ctx1["a"] = 1
            with RequestContext() as ctx2:
                ctx2["a"] = 2
                assert ctx2["a"] == 2
            assert ctx1["a"] == 1

    def test_in_operator(self):
        with RequestContext() as ctx:
            ctx["x"] = 10
            assert "x" in ctx
            assert "y" not in ctx

    def test_delete_item(self):
        with RequestContext() as ctx:
            ctx["key"] = "value"
            del ctx["key"]
            assert "key" not in ctx

    def test_set_method(self):
        with RequestContext() as ctx:
            ctx.set("name", "test")
            assert ctx["name"] == "test"

    def test_data_property(self):
        with RequestContext() as ctx:
            ctx["a"] = 1
            ctx["b"] = 2
            assert ctx.data == {"a": 1, "b": 2}
