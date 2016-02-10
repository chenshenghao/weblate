# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2016 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from datetime import timedelta

from six import StringIO

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from weblate.billing.models import Plan, Billing, Invoice
from weblate.trans.models import Project


class BillingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='bill')
        self.plan = Plan.objects.create(name='test', limit_projects=1, price=0)
        self.billing = Billing.objects.create(user=self.user, plan=self.plan)
        self.invoice = Invoice.objects.create(
            billing=self.billing,
            start=timezone.now().date() - timedelta(days=2),
            end=timezone.now().date() + timedelta(days=2),
            payment=10,
        )
        self.projectnum = 0

    def add_project(self):
        name = 'test{0}'.format(self.projectnum)
        self.projectnum += 1
        self.billing.projects.add(
            Project.objects.create(name=name, slug=name)
        )

    def test_limit_projects(self):
        self.assertTrue(self.billing.in_limits())
        self.add_project()
        self.assertTrue(self.billing.in_limits())
        self.add_project()
        self.assertFalse(self.billing.in_limits())

    def test_commands(self):
        out = StringIO()
        call_command('billing_check', stdout=out)
        self.assertEqual(out.getvalue(), '')
        self.add_project()
        self.add_project()
        out = StringIO()
        call_command('billing_check', stdout=out)
        self.assertEqual(
            out.getvalue(),
            'Following billings are over limit:\n'
            ' * test0, test1: bill (test)\n'
        )
        self.invoice.delete()
        out = StringIO()
        call_command('billing_check', stdout=out)
        self.assertEqual(
            out.getvalue(),
            'Following billings are over limit:\n'
            ' * test0, test1: bill (test)\n'
            'Following billings are past due date:\n'
            ' * test0, test1: bill (test)\n'
        )

    def test_invoice_validation(self):
        invoice = Invoice(
            billing=self.billing,
            start=self.invoice.start,
            end=self.invoice.end,
            payment=30
        )
        # Full overlap
        self.assertRaises(
            ValidationError,
            invoice.clean
        )

        # Start overlap
        invoice.start = self.invoice.end + timedelta(days=1)
        self.assertRaises(
            ValidationError,
            invoice.clean
        )

        # Zero interval
        invoice.end = self.invoice.end + timedelta(days=1)
        self.assertRaises(
            ValidationError,
            invoice.clean
        )

        # Valid after existing
        invoice.end = self.invoice.end + timedelta(days=2)
        invoice.clean()

        # End overlap
        invoice.start = self.invoice.start - timedelta(days=4)
        invoice.end = self.invoice.end
        self.assertRaises(
            ValidationError,
            invoice.clean
        )

        # Valid before existing
        invoice.end = self.invoice.start - timedelta(days=1)
        invoice.clean()

        # Validation of existing
        self.invoice.clean()
