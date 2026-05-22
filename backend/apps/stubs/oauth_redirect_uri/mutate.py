"""Stub 2.14 — redirect URI mutation generation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class MutationClass(str, Enum):
    FOREIGN_ORIGIN = "foreign_origin"
    HOST_SUFFIX = "host_suffix"
    HOST_PREFIX = "host_prefix"
    SCHEME_DOWNGRADE = "scheme_downgrade"
    PATH_PREFIX = "path_prefix"
    PATH_TRAVERSAL = "path_traversal"
    ENCODED_HOST = "encoded_host"
    USERINFO_CONFUSION = "userinfo_confusion"


@dataclass(frozen=True)
class RedirectUriMutation:
    mutation_class: MutationClass
    mutated_uri: str
    baseline_uri: str
    scanner_origin: str


def generate_mutations(
    baseline_redirect_uri: str,
    scanner_origin: str,
    max_probes: int = 8,
) -> list[RedirectUriMutation]:
    """Generate at most `max_probes` mutated redirect URIs from `baseline_redirect_uri`."""
    b = urlparse(baseline_redirect_uri)
    s = urlparse(scanner_origin)

    if not b.netloc or not s.netloc:
        return []

    scanner_host = s.netloc
    trusted_host = b.netloc
    trusted_path = b.path or "/oauth/callback"

    candidates: list[tuple[MutationClass, str]] = [
        (MutationClass.FOREIGN_ORIGIN,
         f"{scanner_origin}{trusted_path}"),
        (MutationClass.HOST_SUFFIX,
         f"{b.scheme}://{trusted_host}.{scanner_host}{trusted_path}"),
        (MutationClass.HOST_PREFIX,
         f"{b.scheme}://{scanner_host}.{trusted_host}{trusted_path}"),
        (MutationClass.SCHEME_DOWNGRADE,
         f"http://{trusted_host}{trusted_path}"),
        (MutationClass.PATH_PREFIX,
         f"{b.scheme}://{trusted_host}{trusted_path}.evil"),
        (MutationClass.PATH_TRAVERSAL,
         f"{b.scheme}://{trusted_host}{trusted_path}/../evil"),
        (MutationClass.ENCODED_HOST,
         f"{b.scheme}://{trusted_host.replace('.', '%2e')}.{scanner_host}{trusted_path}"),
        (MutationClass.USERINFO_CONFUSION,
         f"{b.scheme}://{trusted_host}@{scanner_host}{trusted_path}"),
    ]

    return [
        RedirectUriMutation(
            mutation_class=cls,
            mutated_uri=uri,
            baseline_uri=baseline_redirect_uri,
            scanner_origin=scanner_origin,
        )
        for cls, uri in candidates[:max_probes]
    ]
