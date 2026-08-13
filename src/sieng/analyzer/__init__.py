"""Detection side. Its scope is wider than carrier/ on purpose.

carrier/ handles only jpg and png, the two formats we can embed into safely.
analyzer/ still handles wav and avi, because its job is inspecting files other people
send us and we do not get to choose their type (PROJECT_STRUCTURE.md 4.8).

The ui must show a different list of supported extensions on the analyze page and the
embed page, or users will assume anything analyzable is also embeddable.
"""
