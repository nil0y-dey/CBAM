"""
Precursor trees. Nodes are installations; the root makes the exported good.

Per tonne of exported good, S = rooted verified set, dS = its frontier, k_t = CF_t CSCF_t:
  D~_i     = (1 + m_t) D_i - k_t BMd_i
  theta~_i = theta_i - k_t BMa_i
  E_t(S)   = D~_root if S is empty, else sum_S w_i theta~_i + sum_dS w_j D~_j
  g_i      = E(S) - E(S + i) = w_i (D~_i - theta~_i - sum_C(i) a_j D~_j)
BMa adds the Column A benchmarks of goods made on site, by mass (IR 2025/2620, eq. 2-4).
"""
import json
import math
from dataclasses import dataclass, field, asdict


@dataclass
class NodeSpec:
    id: str
    name: str
    parent: str            # '' for the root
    output_cn8: str        # good shipped to parent
    origin: str            # as in the default tables
    route: str             # Column A route ('' if none)
    a: float               # t per t of parent output
    prior_key: str         # prior_means.csv key
    size: str              # cost class: small/medium/large
    own: bool = False      # exporter's own plant
    internal: list = field(default_factory=list)  # made on site: (cn8, route, t/t)
    note: str = ""


@dataclass
class Node:
    id: str
    name: str
    parent: str
    depth: int
    output_cn8: str
    origin: str
    route: str
    a: float
    w: float
    D_base: float
    default_route: str
    BMd: dict              # year -> t CO2e / t
    BMa: dict              # year -> t CO2e / t
    theta_mean: float
    theta_cv: float
    ln_mu: float
    ln_sigma: float
    cost: float
    cost_low: float
    cost_high: float
    rho: float
    size: str
    own: bool
    prior_source: str
    internal: list
    note: str
    children: list = field(default_factory=list)


@dataclass
class Tree:
    id: str
    title: str
    lesson: str
    sector: str
    country: str
    Q: float               # t/yr to the EU
    lam: float             # share of saving captured
    nodes: dict            # id -> Node, root first
    comext_note: str = ""

    @property
    def root(self):
        return next(iter(self.nodes.values()))

    def children(self, i):
        return [self.nodes[c] for c in self.nodes[i].children]

    # per-tonne quantities
    def D_tilde(self, i, year, policy):
        n = self.nodes[i]
        return (1 + policy.m(year)) * n.D_base - policy.deduction(year) * n.BMd[year]

    def theta_tilde(self, i, theta, year, policy):
        return theta - policy.deduction(year) * self.nodes[i].BMa[year]

    def gain(self, i, theta, year, policy):
        """Certificates saved per t of exported good by adding i (parent in S), no floor."""
        n = self.nodes[i]
        upstream = sum(c.a * self.D_tilde(c.id, year, policy) for c in self.children(i))
        return n.w * (self.D_tilde(i, year, policy) - self.theta_tilde(i, theta, year, policy) - upstream)

    def frontier(self, S):
        return [c for i in S for c in self.nodes[i].children if c not in S]

    def is_rooted(self, S):
        return all(i == self.root.id or self.nodes[i].parent in S for i in S)

    def E(self, S, thetas, year, policy, floor=True):
        """Certificates per t of exported good with verified set S. thetas: id -> theta."""
        S = set(S)
        if not S:
            val = self.D_tilde(self.root.id, year, policy)
        else:
            if not self.is_rooted(S):
                raise ValueError(f"{sorted(S)} is not a rooted subtree")
            val = sum(self.nodes[i].w * self.theta_tilde(i, thetas[i], year, policy) for i in S)
            val += sum(self.nodes[j].w * self.D_tilde(j, year, policy) for j in self.frontier(S))
        return max(0.0, val) if floor else val

    # output
    def to_dict(self):
        d = {k: v for k, v in asdict(self).items() if k != "nodes"}
        d["nodes"] = [asdict(n) for n in self.nodes.values()]
        return d

    def save_json(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def lognormal_params(mean, cv):
    s2 = math.log(1 + cv * cv)
    return math.log(mean) - s2 / 2, math.sqrt(s2)


def build_tree(tid, title, lesson, sector, country, specs, tables, priors, assumptions, years,
               Q=None, lam=None, comext_note=""):
    A = assumptions
    nodes = {}
    for s in specs:
        parent = nodes.get(s.parent) if s.parent else None
        if s.parent and parent is None:
            raise ValueError(f"{tid}: parent {s.parent} of {s.id} must be listed before it")
        D_base, d_route = tables.default(s.origin, s.output_cn8)
        if (s.prior_key, s.origin) not in priors:
            raise KeyError(f"{tid}: no prior mean '{s.prior_key}' for {s.origin} in prior_means.csv")
        prior = priors[(s.prior_key, s.origin)]
        mean = float(prior["theta_direct_tco2e_per_t"])
        cv = A["prior_cv_own_installation" if s.own else "prior_cv_supplier"]["central"]
        mu, sig = lognormal_params(mean, cv)
        BMd = {y: tables.benchmark(s.output_cn8, "B", d_route, y) for y in years}
        BMa = {}
        for y in years:
            v = tables.benchmark(s.output_cn8, "A", s.route, y)
            for cn, rt, mass in s.internal:
                v += mass * tables.benchmark(cn, "A", rt, y)
            BMa[y] = v
        central = A[f"verification_cost_central_{s.size}"]
        rng = A[f"verification_cost_{s.size}_installation"]
        node = Node(id=s.id, name=s.name, parent=s.parent, depth=(parent.depth + 1) if parent else 0,
                    output_cn8=s.output_cn8, origin=s.origin, route=s.route,
                    a=1.0 if parent is None else s.a, w=1.0 if parent is None else parent.w * s.a,
                    D_base=D_base, default_route=d_route, BMd=BMd, BMa=BMa,
                    theta_mean=mean, theta_cv=cv, ln_mu=mu, ln_sigma=sig,
                    cost=central["central"], cost_low=rng["low"], cost_high=rng["high"],
                    rho=A["verification_success_probability"]["central"], size=s.size, own=s.own,
                    prior_source=f"{prior['source']}: {prior['derivation']}", internal=list(s.internal),
                    note=s.note)
        nodes[s.id] = node
        if parent:
            parent.children.append(s.id)
    if Q is None:
        Q = A["eu_volume_aluminium_exporter" if sector == "aluminium" else "eu_volume_steel_exporter"]["central"]
    if lam is None:
        lam = A["pass_through_share"]["central"]
    return Tree(tid, title, lesson, sector, country, Q, lam, nodes, comext_note)


def check_tree(tree, policy, years):
    """Largest |E(S) - E(S+i) - g_i| over nodes and years, floor off. Should be ~0."""
    thetas = {i: n.theta_mean for i, n in tree.nodes.items()}
    worst = 0.0
    for y in years:
        order = list(tree.nodes)   # parents first
        S = []
        for i in order:
            before = tree.E(S, thetas, y, policy, floor=False)
            after = tree.E(S + [i], thetas, y, policy, floor=False)
            worst = max(worst, abs((before - after) - tree.gain(i, thetas[i], y, policy)))
            S.append(i)
    return worst
