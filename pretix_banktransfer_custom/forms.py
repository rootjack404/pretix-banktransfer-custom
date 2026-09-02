#
# This file is part of pretix (Community Edition).
#
# Copyright (C) 2014-2020  Raphael Michel and contributors
# Copyright (C) 2020-today pretix GmbH and contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation in version 3 of the License.
#
# ADDITIONAL TERMS APPLY: Pursuant to Section 7 of the GNU Affero General Public License, additional terms are
# applicable granting you additional permissions and placing additional restrictions on your usage of this software.
# Please refer to the pretix LICENSE file to obtain the full terms applicable to this work. If you did not receive
# this file, see <https://pretix.eu/about/en/license>.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License along with this program.  If not, see
# <https://www.gnu.org/licenses/>.
#
import os

from django import forms
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _


class PaymentProofUploadForm(forms.Form):
    file = forms.FileField(
        label=_('Proof of payment'),
        help_text=_('Upload a screenshot or PDF of your bank transfer confirmation.'),
        required=True,
    )

    def clean_file(self):
        data = self.cleaned_data.get('file')
        if not isinstance(data, UploadedFile):
            return data

        max_size = settings.FILE_UPLOAD_MAX_SIZE_OTHER
        if data.size > max_size:
            raise forms.ValidationError(
                _('Please do not upload files larger than {size} MB!').format(
                    size=max_size // (1024 * 1024),
                )
            )

        ext = os.path.splitext(data.name)[1].lower()
        if ext not in settings.FILE_UPLOAD_EXTENSIONS_OTHER:
            raise forms.ValidationError(_('Filetype not allowed!'))

        return data
