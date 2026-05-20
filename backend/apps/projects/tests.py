from django.test import TestCase

from .models import Project


class ProjectModelTests(TestCase):
    def test_create_project(self) -> None:
        project = Project.objects.create(name="acme", description="bug bounty 2026")
        assert project.id is not None
        assert project.created_at is not None
        assert project.updated_at is not None
        assert str(project) == "acme"

    def test_description_optional(self) -> None:
        project = Project.objects.create(name="minimal")
        assert project.description == ""
