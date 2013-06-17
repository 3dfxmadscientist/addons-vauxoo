# -*- encoding: utf-8 -*-
#!/usr/bin/python
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://openerp.com.ve>).
#    All Rights Reserved
###############Credits######################################################
#    Coded by: Katherine Zaoral <katherine.zaoral@vauxoo.com>
#    Coded by: Yanina Aular <yanina.aular@vauxoo.com>
#    Planified by: Humberto Arocha <hbto@vauxoo.com>
#    Audited by: Nhomar Hernandez <nhomar@vauxoo.com>
#############################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
################################################################################

from osv import osv
from osv import fields

from tools.translate import _

class ifrs_ifrs(osv.osv):

    _name = 'ifrs.ifrs'
    _rec_name = 'code'

    def onchange_company_id(self,cr,uid,ids,company_id,context=None):
        context = context or {}
        context['company_id']=company_id
        res = {'value':{}}
        
        if not company_id: return res
            
        cur_id = self.pool.get('res.company').browse(
                cr, uid, company_id, context=context).currency_id.id
        fy_id = self.pool.get('account.fiscalyear').find(
                cr, uid, context=context)

        res['value'].update({'fiscalyear_id':fy_id})
        res['value'].update({'currency_id':cur_id})
        return res

    _columns = {
        'name' : fields.char('Name', 128, required = True ),
        'company_id' : fields.many2one('res.company', string='Company', ondelete='cascade' ),
        'currency_id': fields.related('company_id', 'currency_id', type='many2one', relation='res.currency', string='Company Currency',help="Currency at which this report will be expressed. If not selected will be used the one set in the company"),
        'title' : fields.char('Title', 128, required = True, translate = True ),
        'code' : fields.char('Code', 128, required = True ),
        'description' : fields.text('Description'),
        'ifrs_lines_ids' : fields.one2many('ifrs.lines', 'ifrs_id', 'IFRS lines' ),
        'state': fields.selection( [
            ('draft','Draft'),
            ('ready', 'Ready'),
            ('done','Done'),
            ('cancel','Cancel') ],
            'State', required=True ),
        'fiscalyear_id' : fields.many2one('account.fiscalyear', 'Fiscal Year' ),
        'do_compute' : fields.boolean('Compute'),
        'ifrs_ids':fields.many2many('ifrs.ifrs', 'ifrs_m2m_rel', 'parent_id', 'child_id', string='Other Reportes',)
    }

    _defaults = {
        'state' : 'draft',
        'company_id': lambda s,c,u,cx: s.pool.get('res.users').browse(
            c,u,u,context=cx).company_id.id,
        'fiscalyear_id': lambda s,c,u,cx: s.pool.get('account.fiscalyear').find(c, u),
    }

    def _get_level(self,cr,uid,l,level,tree,context=None):
        context = context or {}
        if not tree.get(level):
            tree[level]={}
        #The search through level should be backwards from the deepest level to
        #the outmost level
        levels = tree.keys()
        levels.sort()
        levels.reverse()
        xlevel=False
        for n in levels:
            xlevel = isinstance(tree[n].get(l.id),(set)) and n or xlevel 
        if not xlevel:
            tree[level][l.id]=set()
        elif xlevel < level:
            tree[level][l.id]=tree[xlevel][l.id]
            del tree[xlevel][l.id]
        else:# xlevel >= level
            return True
        for j in set(l.total_ids + l.operand_ids):
            tree[level][l.id].add(j.id)
            self._get_level(cr,uid,j,level+1,tree,context=context) 
        return True
    
    def _get_ordered_lines(self, cr, uid, ids, context=None):
        """ Return list of browse ifrs_lines per level in order ASC, for can
        calculate in order of depending.
        
        Retorna la lista de ifrs.lines del ifrs_id organizados desde el nivel
        mas bajo hasta el mas alto. Lo niveles mas bajos se deben calcular
        primero, por eso se posicionan en primer lugar de la lista.
        """
        context = context or {}
        ids = isinstance(ids, (int, long)) and [ids] or ids
        ifrs_brw = self.browse(cr,uid,ids[0],context=context)
        tree = {1:{}}
        level = 1
        for l in ifrs_brw.ifrs_lines_ids:
            self._get_level(cr,uid,l,level,tree,context=context) 
        levels = tree.keys()
        levels.sort()
        levels.reverse()
        ids_o = [i.id for i in ifrs_brw.ifrs_lines_ids]
        ids_x = [] #List of ids per level in order ASC
        for i in levels:
            ids_x += tree[i].keys()
        ifrs_lines = self.pool.get('ifrs.lines')
        res = []
        res = ifrs_lines.browse(cr, uid, ids_x , context=context)#List of browse per level in order ASC
        return res

    def compute(self, cr, uid, ids, context=None):
        context = context or {}
        ids = isinstance(ids, (int, long)) and [ids] or ids
        fy = self.browse(cr, uid, ids, context=context)[0]
        context.update({'whole_fy':True, 'fiscalyear':fy.fiscalyear_id.id})
        ifrs_lines = self.pool.get('ifrs.lines')
       
        list_level = self._get_ordered_lines(cr, uid, ids, context=context)
        
        for ifrs_l in list_level:
            ifrs_lines._get_sum_2(cr, uid, ifrs_l.id, False, context=context)
        return True
    
    def _get_periods_name_list(self, cr, uid, ids, fiscalyear_id, context=None):
        if context is None: context = {}

        """devuelve una lista con la info de los periodos fiscales (numero mes, id periodo, nombre periodo)"""

        period_list = []
        period_list.append( ('0', None , ' ' ) ) 

        fiscalyear_bwr = self.pool.get('account.fiscalyear').browse(cr, uid, fiscalyear_id, context=context)
        
        periods_ids = fiscalyear_bwr._get_fy_period_ids()

        periods = self.pool.get('account.period')
        
        for ii, period_id in enumerate(periods_ids, start=1):
            period_list.append((str(ii), period_id, periods.browse(cr, uid, period_id, context=context).name ))

        return period_list
    
    def _get_period_print_info(self, cr, uid, ids, period_id, report_type, context=None):
        if context is None: context = {}
        ''' Return all the printable information about period'''
        if report_type == 'all':
            res = 'All Periods of the fiscalyear.'
        else:
            period = self.pool.get('account.period').browse(cr, uid, period_id, context = context)
            res = str(period.name) + ' [' + str(period.code) + ']'
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default.update({
            'do_compute' : False,
        })
        res = super(ifrs_ifrs, self).copy(cr, uid, id, default, context)

        return res


class ifrs_lines(osv.osv):

    _name = 'ifrs.lines'
    _parent_store = True
#    _parent_name = "parent_id"
    _order = 'sequence, type'


    def _get_sum_total_2(self, cr, uid, brw, number_month,context = None):
        """ Calculates the sum of the line total_ids the current ifrs.line
        """
        if context is None: context = {}
        res = 0

        #If the report is two or twelve columns, will choose the field needed to make the sum
        if context.get('whole_fy',False):
            field_name = 'amount'
        else:
            field_name = 'period_%s' % str(number_month)

        #It takes the sum of the total_ids
        for t in brw.total_ids:
            res += getattr(t, field_name)
        return res
    
    def _get_sum_2( self, cr, uid, id, number_month, context = None ):
        fy_obj = self.pool.get('account.fiscalyear')
        period_obj = self.pool.get('account.period')
        if context is None: context = {}
        res = 0
        c = context.copy()
        brw = self.browse( cr, uid, id, context = c )
        
        #~ Assembling context
        #~ Generic context applicable to the different types
        if not c.get('fiscalyear'):
            c['fiscalyear']=fy_obj.find(cr,uid,dt=None,context=c)
        
        if not c.get('period_from',False) and not c.get('period_to',False):
            if context.get('whole_fy',False):
                c['period_from'] = period_obj.search(cr,uid,[('fiscalyear_id','=',c['fiscalyear']),('special','=',True)])
                if not c['period_from']:
                    raise osv.except_osv(_('Error !'), _('There are no special period in %s')%(fy_obj.browse(cr,uid,c['fiscalyear'],context=c).name))
                c['period_from']=c['period_from'][0]
            c['period_to'] =period_obj.search(cr,uid,[('fiscalyear_id','=',c['fiscalyear'])])[-1]
        
        c.get('periods') and c.pop('periods')
        c.get('initial_bal') and c.pop('initial_bal')
        
        if brw.type == 'detail':
            if brw.acc_val=='init':
                period_ids = period_obj.build_ctx_periods_initial(cr, uid, c['period_from'])
                c['periods'] = period_ids
                period_company_id = period_obj.browse(cr, uid, c['period_from'], context=context).company_id.id
            if not c['period_from']:
                    raise osv.except_osv(_('Error !'), _('prueba001 %s')%(period_obj.browse(cr,uid,context['period_from'],context=c).name))

            elif brw.acc_val=='var':
                if context.get('whole_fy',False):
                    c['period_from'] =period_obj.search(cr,uid,[('fiscalyear_id','=',c['fiscalyear'],)])
                    if not c['period_from']:
                        raise osv.except_osv(_('Error !'), _('There are no periods in %s')%(fy_obj.browse(cr,uid,c['fiscalyear'],context=c).name))
                    
                if isinstance( c['period_from'], (int, long) ):
                    c['period_from']=c['period_from']
                else:
                    c['period_from']=c['period_from'][1]
                    
        elif brw.type == 'total':
            if brw.comparison <> 'without':
                c2 = c.copy()




                c2['period_from'] = period_obj.previous(cr, uid, c2['period_from'],context= c2)
                if not c2['period_from']:
                    raise osv.except_osv(_('Error !'), _('There are previous period to %s')%(period_obj.browse(cr,uid,c['period_from'],context=c).name))
                c2['period_to']=c2['period_from']
                
        
        
        #~ Stuffing the sum
        brw = self.browse( cr, uid, id, context = c )
        
        if brw.type == 'abstract':
            pass
        elif brw.type == 'constant':
            if brw.constant_type == 'period_days':
                res = period_obj._get_period_days(cr, uid, c['period_from'], c['period_to'])
            elif brw.constant_type == 'fy_periods':
                res = fy_obj._get_fy_periods(cr, uid, c['fiscalyear'])
            elif brw.constant_type == 'fy_month':
                res = fy_obj._get_fy_month(cr, uid, c['fiscalyear'],c['period_to'])
        elif brw.type == 'detail': 
            #Si es de tipo detail
            analytic = [an.id for an in brw.analytic_ids] #Tomo los ids de las cuentas analiticas de las lineas
            if analytic: #Si habian cuentas analiticas en la linea, se guardan en el context y se usan en algun metodo dentro del modulo de account
                c['analytic'] = analytic
            c['partner_detail'] = c.get('partner_detail')
            for a in brw.cons_ids: #Se hace la sumatoria de la columna balance, credito o debito. Dependiendo de lo que se escoja en el wizard
                if brw.value == 'debit':
                    res += a.debit
                elif brw.value == 'credit':
                    res += a.credit
                else:
                    res += a.balance
                    
        elif brw.type == 'total':
            res = self._get_sum_total_2(cr, uid, brw, number_month,context = c)
            if brw.comparison <> 'without':
                res2=0
                #~ TODO: Write definition for previous periods
                #~ that will be the arguments for the new brw.
                
                brw = self.browse( cr, uid, id, context = c2 )
                res2 = self._get_sum_total_2(cr, uid, brw, number_month,context = c2)

                if brw.comparison == 'subtract':
                    res -= res2
                elif brw.comparison == 'percent':
                    res =  res2 != 0 and (100 * res / res2) or 0.0
                elif brw.comparison == 'ratio':
                    res =  res2 != 0 and (res / res2) or 0.0
        res = brw.inv_sign and (-1.0 * res) or res    
        # guardar amount del periodo que corresponde
        if context.get('whole_fy', False):
            field_name = 'amount'
        else:
            field_name = 'period_%s' % str(number_month)
        self.write(cr, uid, brw.id, {field_name : res})
             
        return res 

    def _consolidated_accounts_sum( self, cr, uid, ids, field_name, arg, context = None ):
        #Se hace la suma de las cuentas y se guarda en el campo amount
        if context is None: context = {}
        res = {}
        for id in ids:
            res[id] = self._get_sum( cr, uid, id, context = context )
        return res

    def _get_level(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for ifrs_line in self.browse(cr, uid, ids, context=context):
            level = 0
            parent = ifrs_line.parent_id
            while parent:
                level += 1
                parent = parent.parent_id
            res[ifrs_line.id] = level
        return res

    def _get_children_and_total(self, cr, uid, ids, context=None):
        #this function search for all the children and all consolidated children (recursively) of the given total ids
        ids3 = []
        ids2 = []
        sql = 'select * from ifrs_lines_rel where parent_id in (' + ','.join(map(str, ids)) + ')' 
        cr.execute(sql)
        childs =  cr.fetchall()
        for rec in childs:
            ids2.append(rec[1])
            self.write(cr, uid, rec[1], {'parent_id':rec[0]})
            rec = self.browse(cr, uid, rec[1], context=context)
            for child in rec.total_ids:
                ids3.append(child.id)
        if ids3:
            ids3 = self._get_children_and_total(cr, uid, ids3, context=context)
        return ids2 + ids3
   

    def _get_changes_on_ifrs(self, cr, uid, ids, context=None):
        if context is None: context = {}
        res = []
        ifrs_brws = self.pool.get('ifrs.ifrs').browse(cr, uid, ids, context = context)
        for brw in ifrs_brws:
            if brw.do_compute:
                for l in brw.ifrs_lines_ids:
                    res.append(l.id)
                #~ TODO: write back False to brw.do_compute with SQL
                #~ INCLUDE A LOGGER
        return res

    def exchange(self, cr, uid, ids, from_amount, to_currency_id, from_currency_id, exchange_date, context=None):
        if context is None: context = {}
        if from_currency_id == to_currency_id:
            return from_amount
        curr_obj = self.pool.get('res.currency')
        context['date'] = exchange_date
        return curr_obj.compute(cr, uid, from_currency_id, to_currency_id, from_amount, context=context)
    
    def _get_amount_value_2(self, cr, uid, ids, ifrs_line, period_info, fiscalyear, exchange_date, currency_wizard, number_month=None, target_move=None, pd=None, undefined=None, two=None, context=None):
        if context is None: context = {}
        """ Returns the amount corresponding to the period of fiscal year
        """
        from_currency_id = ifrs_line.ifrs_id.company_id.currency_id.id
        to_currency_id = currency_wizard
        
        if number_month:
            if two:
                context = {'period_from': number_month, 'period_to':number_month}
            else:
                period_id = period_info[number_month][1]
                context = {'period_from': period_id, 'period_to':period_id}
        else:
            context = {'whole_fy': 'True'} 

        context['partner_detail'] = pd 
        context['fiscalyear'] = fiscalyear
        context['state'] = target_move
        
        res = self._get_sum_2(cr, uid, ifrs_line.id, number_month,context = context)
        
        if ifrs_line.type == 'detail':
            res = self.exchange(cr, uid, ids, res, to_currency_id, from_currency_id, exchange_date, context=context)
        elif ifrs_line.type == 'total':
            if ifrs_line.operator not in ('percent','ratio'):
                if ifrs_line.comparison not in ('percent','ratio','product'):
                    res = self.exchange(cr, uid, ids, res, to_currency_id, from_currency_id, exchange_date, context=context)
        return res
    
    def _get_amount_with_operands(self, cr, uid, ids, ifrs_line, period_info, fiscalyear, exchange_date, currency_wizard, number_month=None, target_move=None, pd=None, undefined=None, two=None, context=None):
        if context is None: context = {}
        """ Integrate operand_ids field in the calculation of the amounts for each line 
        """
        
        if not number_month:
            context = {'whole_fy': 'True'} 

        if context.get('whole_fy', False):
            field_name = 'amount'
        else:
            field_name = 'period_%s' % str(number_month)
             
        res = self._get_amount_value_2(cr, uid, ids, ifrs_line, period_info, fiscalyear, exchange_date, currency_wizard, number_month, target_move, pd, undefined, two, context=context)
        
        band = True
        if ifrs_line.operator in ('subtract','percent','ratio','product'):
            res2=0
            for o in ifrs_line.operand_ids:
                res2 += getattr(o, field_name)
            
            if ifrs_line.operator == 'subtract':
                res -= res2
            elif ifrs_line.operator == 'percent':
                res =  res2 != 0 and (100 * res / res2) or 0.0
            elif ifrs_line.operator == 'ratio':
                res =  res2 != 0 and (res / res2) or 0.0
            elif ifrs_line.operator == 'product':
                res =  res * res2
            self.write(cr, uid, ifrs_line.id, {field_name : res})
            ifrs_line = self.browse(cr, uid, ifrs_line.id, context=context)
            band = False 
        
        if band and ifrs_line.type == 'total':
            res = self._get_amount_value_2(cr, uid, ids, ifrs_line, period_info, fiscalyear, exchange_date, currency_wizard, number_month, target_move, pd, undefined, two, context=context)
        
        return res

    def _get_partner_detail(self, cr, uid, ids, ifrs_l, context=None):
        ifrs = self.pool.get('ifrs.lines')
        aml_obj = self.pool.get('account.move.line')
        account_obj = self.pool.get('account.account')
        partner_obj = self.pool.get('res.partner')
        res = []
        if ifrs_l.type =='detail':
            ids2 = [lin.id for lin in ifrs_l.cons_ids]
            ids3 = ids2 and account_obj._get_children_and_consol(cr, uid, ids2, context=context) or []
            if ids3:
                cr.execute(""" SELECT rp.id
                    FROM account_move_line l JOIN res_partner rp ON rp.id = l.partner_id
                    WHERE l.account_id IN %s
                    GROUP BY rp.id 
                    ORDER BY rp.name ASC""", ( tuple(ids3), ) 
                    )
                dat = cr.dictfetchall()
                res = [lins for lins in partner_obj.browse( cr, uid, [li['id'] for li in dat], context=context )]
        return res
    
    _columns = {
        'sequence' : fields.integer( 'Sequence', required = True ),
        'name' : fields.char( 'Name', 128, required = True, translate = True ),
        'type': fields.selection(
           [
                ('abstract','Abstract'),
                ('detail', 'Detail'),
                ('constant', 'Constant'),
                ('total','Total') ] ,
            string = 'Type',
            required = True ),
        'constant_type': fields.selection(
           [
                ('period_days','Days of Period'),
                ('fy_periods',"FY's Periods"),
                ('fy_month',"FY's Month"),
            ],
            string = 'Constant Type',
            required = False ),
        'ifrs_id' : fields.many2one('ifrs.ifrs', 'IFRS', required = True ),
        'amount' : fields.float(string='Amount', help='Total of all periods amount for line'),
        'cons_ids' : fields.many2many('account.account', 'ifrs_account_rel', 'ifrs_lines_id', 'account_id', string='Consolidated Accounts' ),
        'analytic_ids' : fields.many2many('account.analytic.account', 'ifrs_analytic_rel', 'ifrs_lines_id', 'analytic_id', string='Consolidated Analytic Accounts'),
        'parent_id' : fields.many2one('ifrs.lines','Parent', select=True, ondelete ='set null', domain="[('ifrs_id','=',parent.id),('type','=','total'),('id','!=',id)]"),
        'parent_abstract_id' : fields.many2one('ifrs.lines','Parent Abstract', select=True, ondelete ='set null', domain="[('ifrs_id','=',parent.id),('type','=','abstract'),('id','!=',id)]"),
        'parent_right' : fields.integer('Parent Right', select=1 ),
        'parent_left' : fields.integer('Parent Left', select=1 ),
        'level': fields.function(_get_level, string='Level', method=True, type='integer',
         store={
            'ifrs.lines': (_get_children_and_total, ['total_ids','parent_id'], 10),
         }),
        'operand_ids' : fields.many2many('ifrs.lines', 'ifrs_operand_rel', 'ifrs_parent_id', 'ifrs_child_id', string='Operands' ),
        'operator': fields.selection( [
            ('subtract', 'Subtraction'),
            ('percent', 'Percentage'),
            ('ratio','Ratio'),
            ('product','Product'),
            ('without','')
            ],
            'Operator', required=False ,
            help='Leaving blank will not take into account Operands'),
        'comparison': fields.selection( [
            ('subtract', 'Subtraction'),
            ('percent', 'Percentage'),
            ('ratio','Ratio'),
            ('without','')],
            'Make Comparison', required=False ,
            help='Make a Comparison against the previous period.\nThat is, period X(n) minus period X(n-1)\nLeaving blank will not make any effects'),
        'acc_val': fields.selection( [
            ('init', 'Initial Values'),
            ('var','Variation in Periods'),
            ('fy', ('FY All'))],
            'Accounting Spam', required=False,
            help='Leaving blank means YTD'),
        'value': fields.selection( [
            ('debit', 'Debit'),
            ('credit','Credit'),
            ('balance', 'Balance')],
            'Accounting Value', required=False,
            help='Leaving blank means Balance'),
        'total_ids' : fields.many2many('ifrs.lines','ifrs_lines_rel','parent_id','child_id',string='Total'),
        'inv_sign' : fields.boolean('Change Sign to Amount'),
        'invisible' : fields.boolean('Invisible'),
        'comment' : fields.text( 'Comments/Question', help='Comments or questions about this ifrs line' ),
        'period_1' : fields.float('Periodo 1'),
        'period_2' : fields.float('Periodo 2'),
        'period_3' : fields.float('Periodo 3'),
        'period_4' : fields.float('Periodo 4'),
        'period_5' : fields.float('Periodo 5'),
        'period_6' : fields.float('Periodo 6'),
        'period_7' : fields.float('Periodo 7'),
        'period_8' : fields.float('Periodo 8'),
        'period_9' : fields.float('Periodo 9'),
        'period_10' : fields.float('Periodo 10'),
        'period_11' : fields.float('Periodo 11'),
        'period_12' : fields.float('Periodo 12'),
    }

    _defaults = {
        'type' : 'abstract',
        'invisible' : False,
        'acc_val' : 'fy',
        'value' : 'balance',
        'level' : 0,
        #'sequence': lambda obj, cr, uid, context: uid,
    }


    def _check_description(self, cr, user, ids):
        for s in self.browse(cr,user,ids):
            #if s.type=='total' and s.parent_id.type!='abstract':
            #    return False
            pass
        return True
    
    _constraints = [
        (_check_description, ('Error: Los padres de las lineas ifrs de tipo total solo pueden tener padres de tipo abstract'), ['parent_id']),
    ]

    _sql_constraints = [('sequence_ifrs_id_unique','unique(sequence,ifrs_id)', 'The sequence already have been set in another IFRS line')]
    
ifrs_lines()




#~ pregunta. comprobacion de la linea... lo hace cuando le da a guardar--- no lo hace a la hora de ingresarlo, puede taer confuciones a la hora que el usuario agregue a mucha gente y luego no sepa a cual se refiere.

#~ buscar, como hacer para que ordene por secuencia, lo que ingreso!
