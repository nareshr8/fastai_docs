#AUTOGENERATED! DO NOT EDIT! File to edit: dev/40_tabular_core.ipynb (unless otherwise specified).

__all__ = ['TabularProc', 'Categorify', 'Normalize', 'FillStrategy', 'FillMissing', 'TabularPreprocessor', 'process_df',
           'TabularLine', 'TensorTabular', 'ReadTabLine']

from ..imports import *
from ..test import *
from ..core import *
from ..data.all import *
from ..notebook.showdoc import show_doc

@docs
class TabularProc():
    "Base class to write a tabular processor for dataframes"
    order = 0
    def __init__(self, cat_names=None, cont_names=None, func=None):
        self.cat_names,self.cont_names = L(cat_names),L(cont_names)
        if func is not None: self.setup,self.__call__ = func,func

    def setup(self, df, trn_idx=None): pass
    def __call__(self, df):  pass

    _docs = dict(setup="Use `df` to set its state, with just `trn_idx` if passed",
                 __call__="Process `df` with the state computed during setup`")

from pandas.api.types import is_numeric_dtype, is_categorical_dtype

class Categorify(TabularProc):
    "Transform the categorical variables to that type."
    order = 1
    def setup(self, df, trn_idx=None):
        self.categories = {}
        for n in self.cat_names:
            col = df[n] if trn_idx is None else df.loc[trn_idx, n]
            self.categories[n] = pd.Categorical(col, ordered=True).categories

    def __call__(self, df):
        for n in self.cat_names:
            df.loc[:,n] = pd.Categorical(df.loc[:,n], categories=self.categories[n], ordered=True)

class Normalize(TabularProc):
    "Normalize the continuous variables."
    order = 2
    def setup(self, df, trn_idx=None):
        self.means,self.stds = {},{}
        for n in self.cont_names:
            assert is_numeric_dtype(df[n]), (f"""Cannot normalize '{n}' column as it isn't numerical.
                Are you sure it doesn't belong in the categorical set of columns?""")
            col = (df[n] if trn_idx is None else df.loc[trn_idx,n]).values
            self.means[n],self.stds[n] = col.mean(),col.std()

    def __call__(self, df):
        for n in self.cont_names: df[n] = (df[n]-self.means[n]) / (1e-7 + self.stds[n])

mk_class('FillStrategy', **{o:o for o in ['median', 'constant', 'most_common']})
FillStrategy.__doc__ = "Namespace containing the various filling strategies"

class FillMissing(TabularProc):
    "Fill the missing values in continuous columns."
    def __init__(self, cat_names=None, cont_names=None, fill_strategy=FillStrategy.median, add_col=True, fill_val=0.):
        super().__init__(cat_names, cont_names)
        self.fill_strategy,self.add_col,self.fill_val = fill_strategy,add_col,fill_val

    def setup(self, df, trn_idx=None):
        self.na_dict = {}
        for n in self.cont_names:
            col = df[n] if trn_idx is None else df.loc[trn_idx,n]
            if pd.isnull(col).sum():
                if self.fill_strategy == FillStrategy.median: filler = col.median()
                elif self.fill_strategy == FillStrategy.constant: filler = self.fill_val
                else: filler = col.dropna().value_counts().idxmax()
                self.na_dict[n] = filler
                if self.add_col:
                    df[n+'_na'] = pd.isnull(df[n])
                    if n+'_na' not in self.cat_names: self.cat_names.append(n+'_na')

    def __call__(self, df):
        for n in self.cont_names:
            if n in self.na_dict:
                if self.add_col: df[n+'_na'] = pd.isnull(df[n])
                df[n] = df[n].fillna(self.na_dict[n])
            elif pd.isnull(df[n]).sum() != 0:
                raise Exception(f"""There are nan values in field {n} but there were none in the training set given at setup.
                Please fix those manually.""")

class TabularPreprocessor():
    "An object that will preprocess dataframes using `procs`"
    def __init__(self, procs, cat_names=None, cont_names=None, inplace=True):
        self.cat_names,self.cont_names,self.inplace = L(cat_names),L(cont_names),inplace
        self.procs = L(p if isinstance(p, type) else partial(TabularProc, func=p) for p in procs).sorted(key='order')

    def __call__(self, df, trn_idx=None):
        "Call each of `self.procs` on `df`, setup on `df[trn_idx]` if not None"
        df = df if self.inplace else df.copy()
        if trn_idx is None:
            for p in self.procs: p(df)
        else:
            self.procs,procs = [],self.procs
            for p in procs:
                p_ = p(cat_names=self.cat_names, cont_names=self.cont_names)
                p_.setup(df, trn_idx=trn_idx)
                p_(df)
                self.cat_names,self.cont_names = p_.cat_names,p_.cont_names
                self.procs.append(p_)
            self.classes = {n:'#na#'+L(df[n].cat.categories, use_list=True) for n,c in df[self.cat_names].items()}
            for p in self.procs:
                if isinstance(p, Normalize): self.means,self.stds = p.means,p.stds
        return df

def process_df(df, splits, procs, cat_names=None, cont_names=None, inplace=True):
    "Process `df` with `procs` and returns the processed dataframe and the `TabularProcessor` associated"
    proc = TabularPreprocessor(procs, cat_names, cont_names, inplace=inplace)
    res = proc(df, trn_idx=splits[0])
    return res,proc

class TabularLine(pd.Series):
    "A line of a dataframe that knows how to show itself"
    def show(self, ctx=None, **kwargs):
        if ctx is None: return self
        else: return ctx.append(self)

class TensorTabular(tuple):

    def get_ctxs(self, max_samples=10, **kwargs):
        n_samples = min(self[0].shape[0], max_samples)
        df = pd.DataFrame(index = range(n_samples))
        return [df.iloc[i] for i in range(n_samples)]

    def display(self, ctxs): display_df(pd.DataFrame(ctxs))

class ReadTabLine(ItemTransform):
    def __init__(self, proc, cols):
        self.proc = proc
        self.col2idx = {c:i for i,c in enumerate(cols)}
        self.o2is = {n: defaultdict(int, {v:i for i,v in enumerate(proc.classes[n])}) for n in proc.cat_names}

    def encodes(self, row):
        cats = [self.o2is[n][row[self.col2idx[n]]] for n in self.proc.cat_names]
        conts = [row[self.col2idx[n]] for n in self.proc.cont_names]
        return TensorTabular((tensor(cats).long(),tensor(conts).float()))

    def decodes(self, o) -> TabularLine:
        dic = {c: self.proc.classes[c][v] for v,c in zip(o[0], self.proc.cat_names)}
        ms = getattr(self.proc, 'means', {c:0 for c in self.proc.cont_names})
        ss = getattr(self.proc, 'stds',  {c:1 for c in self.proc.cont_names})
        dic.update({c: (v*ss[c] + ms[c]).item() for v,c in zip(o[1], self.proc.cont_names)})
        return pd.Series(dic)