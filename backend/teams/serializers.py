"""Team serializers: team CRUD, membership, readiness, and role holdings.

These were split out of ``workflows.serializers`` (and the team-wide holding out
of ``organisation.serializers``) so the ``teams`` app owns the whole Team feature
— its HTTP shapes included — rather than borrowing them from the apps it
happens to route through. The workflow-configuration serializers
(``WorkflowSerializer``, ``WorkflowWriteSerializer``, ``SectionMemberSerializer``)
stay in ``workflows``; the service functions they and these call still live in
``workflows.services`` and ``organisation.services``.
"""

from rest_framework import serializers

from users.models import User

from roles.models import ApproverRole
from campuses.models import Campus
from roles.serializers import WideRoleAssignmentSerializer
from teams.models import Team, TeamRoleAssignment
from chains.models import Section
from chains.services import workflow_section_roles
from chains.services.lifecycle import create_team, update_team
from roles.services import add_team_member, create_team_role_assignment
