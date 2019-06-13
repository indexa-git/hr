# Copyright 2015 Pedro M. Baeza <pedro.baeza@tecnativa.com>
# Copyright 2017 Vicent Cubells <vicent.cubells@tecnativa.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    invoice_count = fields.Integer(
        compute='_compute_invoice_count',
    )

    @api.multi
    def action_sheet_move_create(self):
        DecimalPrecision = self.env['decimal.precision']
        precision = DecimalPrecision.precision_get('Product Price')
        expense_line_ids = \
            self.mapped('expense_line_ids').filtered('invoice_id')
        res = super(HrExpenseSheet, self).action_sheet_move_create()
        move_lines = self.env['account.move'].search(
            [('ref', 'in', self.mapped('name'))],
        ).mapped('line_ids')
        for line in expense_line_ids:
            partner = line.invoice_id.partner_id.commercial_partner_id
            c_move_lines = move_lines.filtered(
                lambda x:
                x.partner_id == partner and
                x.debit == line.invoice_id.residual and
                not x.reconciled
            )
            if len(c_move_lines) > 1:
                c_move_lines = c_move_lines[0]
            residual = line.invoice_id.residual
            c_move_lines |= line.invoice_id.move_id.line_ids.filtered(
                lambda x:
                x.account_id == line.invoice_id.account_id and
                float_compare(x.credit, residual, precision) == 0)
            if len(c_move_lines) != 2:
                raise UserError(
                    _('Cannot reconcile supplier invoice payable with '
                      'generated line. Please check amounts and see '
                      'if the invoice is already added or paid. '
                      'Invoice: %s') % line.invoice_id.number)
            c_move_lines.reconcile()
        return res

    @api.multi
    def _compute_invoice_count(self):
        Invoice = self.env['account.invoice']
        can_read = Invoice.check_access_rights('read', raise_exception=False)
        for sheet in self:
            sheet.invoice_count = can_read and \
                len(sheet.expense_line_ids.mapped('invoice_id')) or 0

    @api.multi
    def action_view_invoices(self):
        self.ensure_one()
        action = {
            'name': _('Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice',
            'target': 'current',
        }
        invoice_ids = self.expense_line_ids.mapped('invoice_id').ids
        view = self.env.ref('account.invoice_supplier_form')
        if len(invoice_ids) == 1:
            invoice = invoice_ids[0]
            action['res_id'] = invoice
            action['view_mode'] = 'form'
            action['views'] = [(view.id, 'form')]
        else:
            action['view_mode'] = 'tree,form'
            action['domain'] = [('id', 'in', invoice_ids)]
        return action
