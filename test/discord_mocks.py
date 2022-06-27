from datetime import datetime, timezone


class MockAuthor:
    def __init__(self, name):
        self.name = name
        self.id = name
        self.display_name = name
        self.roles = []


class MockMessage:
    def __init__(self, content, author, channel):
        self.content = content
        self.author = MockAuthor(author)
        self.channel = MockChannel(author, channel)
        self.clean_content = content.lower()
        self.created_at = datetime.now(timezone.utc)
        self.id = author
        self.mentions = []

    def __repr__(self):
        return f"MockMessage({self.content})"


class MockGuild:
    def __init__(self, name):
        self.id = name


class MockChannel:
    def __init__(self, author_name, name):
        self.id = name
        self.name = name
        self.guild = MockGuild(name)
        self.recipient = MockAuthor(author_name)

    def __repr__(self):
        return f"MockChannel({self.id})"
