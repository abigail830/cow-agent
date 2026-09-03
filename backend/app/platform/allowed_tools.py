"""Parse profile.yaml allowed_tools (MAF function names) into MCP filters."""

from __future__ import annotations


def _postgres_remote_alias(remote: str) -> str:
    """Map profile tool suffixes to mcp-postgres remote tool names."""
    legacy = {
        "run_query": "query_data",
        "query": "query_data",
    }
    return legacy.get(remote, remote)


def _mysql_remote_alias(remote: str) -> str:
    """Map profile tool suffixes to @benborla29/mcp-server-mysql remote tool names."""
    legacy = {
        "execute_query": "mysql_query",
        "query": "mysql_query",
        "query_data": "mysql_query",
        "run_query": "mysql_query",
    }
    return legacy.get(remote, remote)


def _remote_alias(server_name: str, remote: str) -> str:
    if server_name == "postgres":
        return _postgres_remote_alias(remote)
    if server_name == "mysql":
        return _mysql_remote_alias(remote)
    return remote


def _maf_remote_tool(entry: str, server_name: str) -> str | None:
    prefix = f"{server_name}_"
    if entry.startswith(prefix):
        remote = entry[len(prefix) :]
        return _remote_alias(server_name, remote)
    mcp_prefix = f"mcp__{server_name}__"
    if entry.startswith(mcp_prefix):
        remote = entry[len(mcp_prefix) :]
        return _remote_alias(server_name, remote)
    return None


def mcp_remote_tools_for_server(profile_entries: list[str], server_name: str) -> list[str] | None:
    """Remote MCP tool names for one server (postgres → list_tables).

    Profile uses MAF exposed names: ``postgres_list_tables`` → remote ``list_tables``.

    Returns None when profile does not list any ``{server}_*`` tools.
    """
    if not profile_entries:
        return None

    remote: list[str] = []
    for entry in profile_entries:
        if entry == "Skill":
            continue
        tool = _maf_remote_tool(entry, server_name)
        if tool:
            remote.append(tool)

    if not remote and not any(
        e != "Skill" and "_" in e and not e.startswith("mcp__") for e in profile_entries
    ):
        return None
    return remote


def runtime_function_allowlist(profile_entries: list[str]) -> set[str] | None:
    """MAF ``function.name`` values the agent may call. None = unrestricted."""
    if not profile_entries:
        return None

    names: set[str] = set()
    for entry in profile_entries:
        if entry == "Skill":
            continue
        names.add(entry)
        if entry.startswith("mcp__"):
            parts = entry.split("__", 2)
            if len(parts) == 3:
                server, remote = parts[1], parts[2]
                names.add(f"{server}_{remote}")
                names.add(_remote_alias(server, remote))
            continue
        if "_" in entry:
            server, _, remote = entry.partition("_")
            if remote:
                alias = _remote_alias(server, remote)
                names.add(alias)
                names.add(f"{server}_{alias}")

    return names or None
