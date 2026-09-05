"""Request router.

First-match-wins pipeline over a precomputed InspectResult (extracted per
protocol by awerouter.protocols):

  L1 Capability guard  — web_search tool declared -> toolRouting.webSearch (default pro)
                         image content present    -> settings.imageModel (default pro)
  L2 Tier label match  — backgroundModel / thinkModel exact-match
  L3 Difficulty score  — long context -> pro; default -> settings.defaultModel (default flash)
  L4 Consequence check — trailing tool batch changed code -> toolRouting.edit (default pro)

The image guard sits in L1, above tier labels and difficulty, because image
routing is a capability decision, not a difficulty guess: with imageModel
flipped to flash (a non-multimodal flagship on pro), an image-bearing request
must reach the multimodal model no matter what tier label it carries or how
long it is.

L4 is a consequence checkpoint, not a difficulty guess: structure cannot see
the turn that decides an edit, but the turn right after code changed is the
review turn (verify, continue, report), so it goes to pro — flash drafts,
pro reviews. It sits below L3 on purpose: a session already above
longContextThreshold stays pro no matter what tool just ran (flash's
capability ceiling and the one-way flash->pro session invariant both win
over the checkpoint).
"""

from __future__ import annotations

from awerouter.protocols import effective_tokens
from awerouter.types import Candidate, Destination, InspectResult, ResolveResult


def build_queue(dest_key: str, profile, feat: InspectResult,
                providers: dict | None = None) -> tuple[Candidate, ...]:
    """Expand a resolved tier into its ordered failover queue.

    Zero config keeps one implicit cross-tier hop per tier (flash→pro is the
    long-standing single-hop rescue; pro→flash answers over erroring — the
    degradation is loud, stamped into the label of every request it saves).
    An explicit backups list replaces the implicit hop for that tier: the
    queue is exactly what was written, nothing appended.

    The L1 image guard filters here too, not just in resolve: a model that
    cannot see images must never receive them during failover either. The
    primary always stands — resolve already made the image decision — only
    fallback candidates need the capability check, against the provider's
    declared 'multimodal' flag (undeclared = False, the safe direction).
    """
    dests = profile.destinations
    declared = profile.backups.get(dest_key, [])
    queue = [Candidate(dest_key, dests[dest_key])]
    queue += [Candidate(dest_key, d) for d in declared]
    if not declared:
        other = "pro" if dest_key == "flash" else "flash"
        queue.append(Candidate(other, dests[other]))
    if feat.has_image and providers is not None:
        # Keep the head; a backup the image guard cannot vouch for is dropped,
        # never silently handed an image it cannot see.
        queue = [queue[0]] + [
            c for c in queue[1:] if providers[c.dest.provider_name].multimodal
        ]
    return tuple(queue)


def build_direct_queue(dest: Destination, feat: InspectResult,
                       providers: dict | None = None) -> tuple[Candidate, ...]:
    """Expand a gateway 'provider/<model>' direct forward into its failover queue.

    Unpooled stays pinned: a length-1 queue, so "never falls back" needs no
    special case in the retry loop — the caller named this exact model, and
    swapping it for another would not be what was asked for. A provider
    'pool' tag opts in: fellow pool members carry the SAME model — the model
    is the request's property, failover only swaps who serves it — in
    providers.json declaration order wrapping around from the named entry,
    so each account's overflow flows to the next account, never silently
    back to a de-facto primary. A member that did not declare the model is
    simply not a candidate (capability, not error).

    The image guard holds on the tail exactly like build_queue: the named
    primary stands (the caller chose it), candidates need 'multimodal'.
    """
    queue = [Candidate("direct", dest)]
    pool = providers[dest.provider_name].pool if providers is not None else ""
    if pool:
        members = [n for n, p in providers.items() if p.pool == pool]
        start = members.index(dest.provider_name)
        for name in members[start + 1:] + members[:start]:
            if dest.model in providers[name].models:
                queue.append(Candidate("direct", Destination(name, dest.model)))
    if feat.has_image and providers is not None:
        queue = [queue[0]] + [
            c for c in queue[1:] if providers[c.dest.provider_name].multimodal
        ]
    return tuple(queue)


def resolve(
    model: str | None,
    feat: InspectResult,
    dests: dict[str, Destination],
    background_model: str,
    think_model: str,
    long_context_threshold: int,
    web_search_model: str = "pro",
    search_discount: float = 0.3,
    tool_edit_dest: str | None = "pro",
    image_dest: str = "pro",
    default_dest: str = "flash",
) -> ResolveResult:
    m = model or ""

    # L1: capability guards ------------------------------------------------
    if feat.has_web_search:
        dest_key = web_search_model
        return ResolveResult(
            destination=dest_key,
            model=dests[dest_key].model,
            label="webSearch",
            inspect=feat,
        )
    if feat.has_image:
        return ResolveResult(
            destination=image_dest,
            model=dests[image_dest].model,
            label="image",
            inspect=feat,
        )

    # L2: tier label match ------------------------------------------------
    if m == background_model:
        return ResolveResult(
            destination="flash",
            model=dests["flash"].model,
            label="background",
            inspect=feat,
        )
    if m == think_model:
        return ResolveResult(
            destination="pro",
            model=dests["pro"].model,
            label="think",
            inspect=feat,
        )

    # L3: difficulty score (cost-first: default -> flash) -----------------
    # File-search results (Grep/Glob/LS) count at settings.searchResultDiscount:
    # bulk they add is cheap for flash to carry, so they must not alone tip the
    # scale to pro.
    if effective_tokens(feat.token_count, feat.file_search_tokens, search_discount) > long_context_threshold:
        return ResolveResult(
            destination="pro",
            model=dests["pro"].model,
            label="longContext",
            inspect=feat,
        )

    # L4: consequence checkpoint -------------------------------------------
    # The trailing tool batch changed code (Edit/Write/apply_patch/...): the
    # next turn judges that change, so it earns pro. Null destination
    # disables the rule; every other phase falls through to the flash default.
    if tool_edit_dest and feat.last_phase == "edit":
        return ResolveResult(
            destination=tool_edit_dest,
            model=dests[tool_edit_dest].model,
            label="toolEdit",
            inspect=feat,
        )

    return ResolveResult(
        destination=default_dest,
        model=dests[default_dest].model,
        label="default",
        inspect=feat,
    )
