"""Tests to verify conftest fixtures work correctly."""


def test_create_route_file_fixture(create_route_file, tmp_path):
    """Verify create_route_file fixture creates files correctly."""
    content = "def get(): return {'test': True}"
    route_file = create_route_file(content=content)

    assert route_file.exists()
    assert route_file.name == "route.py"
    assert route_file.read_text() == content
    assert route_file.parent == tmp_path


def test_create_route_file_with_subdir(create_route_file, tmp_path):
    """Verify create_route_file can create files in subdirectories."""
    content = "def post(): pass"
    route_file = create_route_file(content=content, subdir="users")

    assert route_file.exists()
    assert route_file == tmp_path / "users" / "route.py"
    assert route_file.read_text() == content


def test_create_route_file_with_nested_subdir(create_route_file, tmp_path):
    """Verify create_route_file can create files in nested subdirectories."""
    content = "async def get(): return {}"
    route_file = create_route_file(content=content, subdir="api/v1/users")

    assert route_file.exists()
    assert route_file == tmp_path / "api" / "v1" / "users" / "route.py"


def test_create_route_tree_simple(create_route_tree, tmp_path):
    """Verify create_route_tree creates simple directory structures."""
    spec = {
        "users": "def get(): return []",
        "posts": "def get(): return []",
    }

    root = create_route_tree(spec)

    assert root == tmp_path
    assert (root / "users" / "route.py").exists()
    assert (root / "posts" / "route.py").exists()
    assert (root / "users" / "route.py").read_text() == "def get(): return []"


def test_create_route_tree_nested(create_route_tree, tmp_path):
    """Verify create_route_tree creates nested directory structures."""
    spec = {
        "api": {
            "v1": {
                "users": "def get(): return []",
            },
        },
    }

    root = create_route_tree(spec)

    route_file = root / "api" / "v1" / "users" / "route.py"
    assert route_file.exists()
    assert route_file.read_text() == "def get(): return []"


def test_create_route_tree_mixed(create_route_tree, tmp_path):
    """Verify create_route_tree handles mixed leaf and branch nodes."""
    spec = {
        "users": "def get(): return []",
        "posts": {
            "[postId]": "def get(postId: int): return {'id': postId}",
        },
    }

    root = create_route_tree(spec)

    assert (root / "users" / "route.py").exists()
    assert (root / "posts" / "[postId]" / "route.py").exists()


def test_simple_route_handler_fixture(simple_route_handler):
    """Verify simple_route_handler fixture returns valid Python code."""
    assert "def get():" in simple_route_handler
    assert "return" in simple_route_handler


def test_async_route_handler_fixture(async_route_handler):
    """Verify async_route_handler fixture returns async function."""
    assert "async def get():" in async_route_handler
    assert "return" in async_route_handler


def test_multi_method_handler_fixture(multi_method_handler):
    """Verify multi_method_handler fixture returns multiple methods."""
    assert "def get():" in multi_method_handler
    assert "def post(" in multi_method_handler
    assert "def delete():" in multi_method_handler


def test_websocket_handler_fixture(websocket_handler):
    """Verify websocket_handler fixture returns WebSocket handler."""
    assert "async def websocket(" in websocket_handler
    assert "websocket.accept()" in websocket_handler


def test_parametric_route_handler_fixture(parametric_route_handler):
    """Verify parametric_route_handler fixture has path parameters."""
    assert "def get(" in parametric_route_handler
    assert "user_id" in parametric_route_handler
