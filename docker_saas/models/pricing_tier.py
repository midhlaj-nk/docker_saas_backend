from odoo import _, fields, models


class DockerPricingTier(models.Model):
    _name = 'docker.pricing.tier'
    _description = 'Docker SaaS Pricing Tier'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(required=True, tracking=True)
    sequence = fields.Integer(default=10, tracking=True)
    code = fields.Char(help="Internal identifier for the tier.", tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    description = fields.Text(tracking=True)
    target_user_count = fields.Char(
        string='Recommended Users',
        help="Recommended concurrent user range (e.g., '10-30 users').",
        tracking=True,
    )
    price_monthly = fields.Float(
        string='Monthly Price',
        help="Suggested monthly price for this tier (informational).",
        tracking=True,
    )

    cpu_limit = fields.Float(
        string='CPU Limit (Odoo)',
        default=2.0,
        help="Maximum CPU cores for the Odoo container.",
        tracking=True,
    )
    cpu_reservation = fields.Float(
        string='CPU Reservation (Odoo)',
        default=1.0,
        help="Minimum guaranteed CPU cores for the Odoo container.",
        tracking=True,
    )
    memory_limit = fields.Char(
        string='Memory Limit (Odoo)',
        default='4g',
        help="Maximum memory for the Odoo container.",
        tracking=True,
    )
    memory_reservation = fields.Char(
        string='Memory Reservation (Odoo)',
        default='1g',
        help="Minimum guaranteed memory for the Odoo container.",
        tracking=True,
    )

    postgres_cpu_limit = fields.Float(
        string='CPU Limit (PostgreSQL)',
        default=1.0,
        help="Maximum CPU cores for the PostgreSQL container.",
        tracking=True,
    )
    postgres_cpu_reservation = fields.Float(
        string='CPU Reservation (PostgreSQL)',
        default=0.5,
        help="Minimum guaranteed CPU cores for the PostgreSQL container.",
        tracking=True,
    )
    postgres_memory_limit = fields.Char(
        string='Memory Limit (PostgreSQL)',
        default='2g',
        help="Maximum memory for the PostgreSQL container.",
        tracking=True,
    )
    postgres_memory_reservation = fields.Char(
        string='Memory Reservation (PostgreSQL)',
        default='1g',
        help="Minimum guaranteed memory for the PostgreSQL container.",
        tracking=True,
    )

    notes = fields.Text(string='Internal Notes')

    def action_apply_to_instances(self):
        self.ensure_one()
        instances = self.env['docker.instance'].search([('pricing_tier_id', '=', self.id)])
        for instance in instances:
            instance._apply_pricing_tier(self)
        action = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Pricing Tier Applied'),
                'message': _('Resources updated on %s linked instances.') % len(instances),
                'type': 'success',
                'sticky': False,
            },
        }
        if instances:
            action['params']['next'] = {
                'type': 'ir.actions.act_window',
                'res_model': 'docker.instance',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', instances.ids)],
            }
        return action

