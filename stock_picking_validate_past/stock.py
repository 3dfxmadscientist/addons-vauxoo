# -*- encoding: utf-8 -*-
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#
#    Copyright (c) 2013 Vauxoo - http://www.vauxoo.com/
#    All Rights Reserved.
#    info Vauxoo (info@vauxoo.com)
############################################################################
#    Coded by: Luis Torres (luis_t@vauxoo.com)
#              fernandoL (fernando_ld@vauxoo.com)
############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import fields, osv
from lxml import etree


class stock_move(osv.osv):
    
    _inherit = 'stock.move'
    
    _columns = {
        'type_process_date': fields.selection([
            ('current_date', 'Current Date'),
            ('planned_date', 'Planned Date'),
        ], string = 'Type Process Date'),
    }
    
    _defaults = {
        'type_process_date': 'current_date',
    }
    
    def action_confirm(self, cr, uid, ids, context=None):
        for id_move in ids:
            move = self.browse(cr, uid, id_move)
        res = super(stock_move, self).action_confirm(cr, uid, ids, context=context)
        for id_move in ids:
            move = self.browse(cr, uid, id_move)
            type_pross_date = move.type_process_date
            date_expect = move.date_expected
            if type_pross_date == 'planned_date':
                self.write(cr, uid, ids, {'create_date': date_expect})
        return res
        
    def action_done(self, cr, uid, ids, context=None):
        res = super(stock_move, self).action_done(cr, uid, ids, context=context)
        for id_move in ids:
            move = self.browse(cr, uid, id_move)
            type_pross_date = move.type_process_date
            date_expect = move.date_expected
            if type_pross_date == 'planned_date':
                self.write(cr, uid, ids, {'date': date_expect})
        return res
    
stock_move()

class stock_inventory(osv.osv):
    
    _inherit = 'stock.inventory'
    
    def action_confirm(self, cr, uid, ids, context=None):
        res = super(stock_inventory, self).action_confirm(cr, uid, ids, context=context)
        move_obj = self.pool.get('stock.move')
        for inv in self.browse(cr, uid, ids, context=context):
            for stk_move in inv.move_ids:
                move_obj.write(cr, uid, stk_move.id, {'date_expected':stk_move.date, 'type_process_date': 'planned_date'}, context=context)
            
        return res
    
stock_inventory()