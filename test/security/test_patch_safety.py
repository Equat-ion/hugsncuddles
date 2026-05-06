def test_apply_patch_rejects_absolute_paths():
    from agent.tools.fs import apply_patch

    patch = """*** Begin Patch
*** Update File: /etc/passwd
@@
-root
+root
*** End Patch"""
    try:
        apply_patch("/tmp", patch)
    except ValueError as exc:
        assert "path" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_apply_patch_rejects_traversal():
    from agent.tools.fs import apply_patch

    patch = """*** Begin Patch
*** Update File: ../../../etc/passwd
@@
-root
+root
*** End Patch"""
    try:
        apply_patch("/tmp", patch)
    except ValueError as exc:
        assert "path" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")