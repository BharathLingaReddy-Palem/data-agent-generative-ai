"""Trusted worker: interprets an analytical expression language, never execs Python."""
import ast
import io
import json
import math
import operator
import os
import sys

if os.name != 'nt':
    import resource
    memory = int(sys.argv[1]) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    cpu = int(sys.argv[2])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))

import numpy as np
import pandas as pd
from pandas.core.groupby.generic import DataFrameGroupBy, SeriesGroupBy
from pandas.core.indexing import _LocIndexer, _iLocIndexer
from pandas.core.strings.accessor import StringMethods
from pandas.core.indexes.accessors import DatetimeProperties


class PolicyError(ValueError):
    pass


METHODS = set('sum mean median min max count size std var quantile nunique unique value_counts '
              'groupby agg aggregate head tail sort_values sort_index round describe corr '
              'select_dtypes isna notna isin between fillna dropna drop_duplicates '
              'drop duplicated stack unstack reset_index rename abs clip cumsum cumprod pct_change diff nlargest'.split()) | {
                  'nsmallest', 'where', 'to_dict', 'tolist', 'to_list', 'astype', 'copy'}
STR_METHODS = set('lower upper strip lstrip rstrip len startswith endswith contains replace split'.split())
PD_FUNCS = {'to_numeric': pd.to_numeric, 'to_datetime': pd.to_datetime, 'isna': pd.isna, 'notna': pd.notna}
NP_FUNCS = {k: getattr(np, k) for k in ('mean','median','sum','min','max','std','var','percentile','sqrt','abs','round','isnan','where')}
TYPES = (pd.DataFrame, pd.Series, pd.Index, DataFrameGroupBy, SeriesGroupBy)
PROPERTIES = {'columns','index','shape','size','dtypes','dtype','T','str','dt','loc','iloc',
              'year','month','day','dayofweek','quarter','days_in_month'}
BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
       ast.BitAnd: operator.and_, ast.BitOr: operator.or_}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Gt: operator.gt,
       ast.GtE: operator.ge, ast.Lt: operator.lt, ast.LtE: operator.le}


class Interpreter:
    def __init__(self, df):
        self.names = {'df': df, 'result': None}
        self.stdout = []

    def evaluate(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str,int,float,bool,type(None))):
            if isinstance(node.value, int) and abs(node.value) > 10**15:
                raise PolicyError('Integer exceeds analytical limit.')
            return node.value
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        if isinstance(node, (ast.List,ast.Tuple)):
            values = [self.evaluate(x) for x in node.elts]
            return tuple(values) if isinstance(node,ast.Tuple) else values
        if isinstance(node, ast.Dict) and all(k is not None for k in node.keys):
            return {self.evaluate(k): self.evaluate(v) for k,v in zip(node.keys,node.values)}
        if isinstance(node, ast.Slice):
            return slice(*(self.evaluate(x) if x else None for x in (node.lower,node.upper,node.step)))
        if isinstance(node, ast.Subscript):
            obj, key = self.evaluate(node.value), self.evaluate(node.slice)
            if not isinstance(obj, TYPES + (list,tuple,dict,np.ndarray,_LocIndexer,_iLocIndexer)):
                raise PolicyError('Indexing this object is not allowed.')
            return obj[key]
        if isinstance(node, ast.Attribute):
            obj = self.evaluate(node.value)
            if node.attr in PROPERTIES and isinstance(obj, TYPES + (DatetimeProperties,)):
                return getattr(obj,node.attr)
            raise PolicyError('Property access is not allowed: ' + node.attr)
        if isinstance(node, ast.BinOp) and type(node.op) in BIN:
            a,b = self.evaluate(node.left),self.evaluate(node.right)
            if isinstance(node.op,ast.Mult) and (isinstance(a,(str,list,tuple)) or isinstance(b,(str,list,tuple))):
                raise PolicyError('Sequence repetition is not allowed.')
            return BIN[type(node.op)](a,b)
        if isinstance(node, ast.UnaryOp):
            value = self.evaluate(node.operand)
            fn = {ast.USub:operator.neg, ast.UAdd:operator.pos, ast.Invert:operator.invert, ast.Not:operator.not_}.get(type(node.op))
            if fn:
                return fn(value)
        if isinstance(node,ast.Compare) and len(node.ops)==1 and type(node.ops[0]) in CMP:
            return CMP[type(node.ops[0])](self.evaluate(node.left),self.evaluate(node.comparators[0]))
        if isinstance(node, ast.Call):
            if any(k.arg is None for k in node.keywords) or any(isinstance(x,ast.Starred) for x in node.args):
                raise PolicyError('Argument expansion is not allowed.')
            args = [self.evaluate(x) for x in node.args]
            kwargs = {k.arg:self.evaluate(k.value) for k in node.keywords}
            if isinstance(node.func,ast.Name):
                funcs = {'len':len,'round':round,'float':float,'int':int,'str':str,'abs':abs}
                if node.func.id=='print':
                    output = ' '.join(str(x) for x in args)
                    if sum(map(len,self.stdout))+len(output)>65536:
                        raise PolicyError('Printed output exceeds 64 KB.')
                    self.stdout.append(output)
                    return None
                if node.func.id in funcs:
                    return funcs[node.func.id](*args,**kwargs)
            if isinstance(node.func,ast.Attribute):
                attr = node.func.attr
                if isinstance(node.func.value,ast.Name) and node.func.value.id in ('pd','np'):
                    funcs = PD_FUNCS if node.func.value.id=='pd' else NP_FUNCS
                    if attr in funcs:
                        return funcs[attr](*args,**kwargs)
                else:
                    obj = self.evaluate(node.func.value)
                    allowed = METHODS if isinstance(obj,TYPES) else STR_METHODS if isinstance(obj,StringMethods) else {'strftime','to_period'} if isinstance(obj,DatetimeProperties) else set()
                    if attr in allowed:
                        if attr in ('agg', 'aggregate'):
                            aggregates = set('sum mean median min max count size std var nunique first last prod'.split())
                            def safe_aggregation(value):
                                if isinstance(value,str):
                                    return value in aggregates
                                if isinstance(value,(list,tuple)):
                                    return all(safe_aggregation(v) for v in value)
                                if isinstance(value,dict):
                                    return all(safe_aggregation(v) for v in value.values())
                                return False
                            if not args or not safe_aggregation(args[0]) or len(args)>1 or kwargs:
                                raise PolicyError('Only named statistical aggregations are allowed.')
                        # Attribute lookup happens only after checking a trusted receiver type.
                        return getattr(obj,attr)(*args,**kwargs)
            raise PolicyError('Function or method is not allowed.')
        raise PolicyError('Unsupported analytical syntax: '+type(node).__name__)

    def run(self, code):
        if len(code)>16384:
            raise PolicyError('Code exceeds 16 KB.')
        tree = ast.parse(code)
        nodes = list(ast.walk(tree))
        if len(nodes)>512:
            raise PolicyError('Code exceeds 512 syntax nodes.')
        for node in nodes:
            if isinstance(node,(ast.Name,ast.Attribute)) and (getattr(node,'id',getattr(node,'attr','')).startswith('_')):
                raise PolicyError('Private names are not allowed.')
        for statement in tree.body:
            if isinstance(statement,ast.Assign) and len(statement.targets)==1 and isinstance(statement.targets[0],ast.Name):
                name = statement.targets[0].id
                if name in ('df','pd','np','print','len'):
                    raise PolicyError('Reserved variable cannot be reassigned.')
                self.names[name] = self.evaluate(statement.value)
            elif isinstance(statement,ast.Expr):
                self.evaluate(statement.value)
            else:
                raise PolicyError('Only assignments and analytical expressions are supported.')
        return self.names['result']


def plain(value):
    if isinstance(value,(pd.DataFrame,pd.Series)):
        if len(value)>1000:
            raise PolicyError('Result exceeds 1000 rows; use head() or aggregate.')
        value = value.to_dict(orient='records') if isinstance(value,pd.DataFrame) else value.to_dict()
    if isinstance(value,dict):
        return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray,pd.Index)):
        if len(value)>10000:
            raise PolicyError('Result contains too many elements.')
        return [plain(v) for v in value]
    if isinstance(value,np.generic):
        return plain(value.item())
    if isinstance(value,float) and not math.isfinite(value) or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value,(str,int,float,bool,type(None))):
        return value
    if isinstance(value,(pd.Timestamp,pd.Period)):
        return str(value)
    raise PolicyError('Unsupported result type.')


if __name__=='__main__':
    try:
        request = json.loads(sys.stdin.read(17*1024*1024))
        df = pd.read_json(io.StringIO(request['data']),orient='table')
        interpreter = Interpreter(df)
        result = plain(interpreter.run(request['code']))
        response = dict(success=True, result=result, stdout='\n'.join(interpreter.stdout), error=None)
        output = json.dumps(response,allow_nan=False)
        if len(output.encode())>1024*1024:
            raise PolicyError('Result exceeds 1 MB.')
    except Exception as exc:
        output = json.dumps(dict(success=False,result=None,stdout='',error=f'{type(exc).__name__}: {str(exc)[:1000]}'))
    sys.stdout.write(output)
