from abc import ABC, abstractmethod


class VisibilityCriterion(ABC):
    @abstractmethod
    def is_visible(self, alt_deg, elong_deg, age_hours=None):
        pass

    @abstractmethod
    def score(self, alt_deg, elong_deg, age_hours=None):
        pass

    @property
    @abstractmethod
    def name(self):
        pass


class OdehCriterion(VisibilityCriterion):
    """ODEH 2004 - en yaygin gozlemsel standart"""

    @property
    def name(self):
        return "odeh"

    def score(self, alt_deg, elong_deg, age_hours=None):
        W = elong_deg
        ARCV = alt_deg
        return ARCV - (7.1651 - 6.3226*(W*0.01) + 7.0482*(W*0.01)**2 - 0.3014*(W*0.01)**3)

    def is_visible(self, alt_deg, elong_deg, age_hours=None):
        return self.score(alt_deg, elong_deg) >= 0.0

    def description(self, q):
        if q >= 0.0:
            return "Acik gozle gorunur"
        elif q >= -0.96:
            return "Optik aracla gorunebilir"
        else:
            return "Gorunmez"


class YallopCriterion(VisibilityCriterion):
    """Yallop 1997"""

    @property
    def name(self):
        return "yallop"

    def score(self, alt_deg, elong_deg, age_hours=None):
        W = elong_deg
        ARCV = alt_deg
        return ARCV - (11.8371 - 6.3226*(W*0.01) + 7.0482*(W*0.01)**2 - 0.3014*(W*0.01)**3)

    def is_visible(self, alt_deg, elong_deg, age_hours=None):
        return self.score(alt_deg, elong_deg) >= -0.014

    def description(self, q):
        if q >= 0.216:
            return "Kolay gorunur (A)"
        elif q >= -0.014:
            return "Gorunur (B)"
        elif q >= -0.160:
            return "Zor gorunur (C)"
        elif q >= -0.232:
            return "Optik arac gerekli (D)"
        elif q >= -0.293:
            return "Optik aracla zor (E)"
        else:
            return "Gorunmez (F)"


class IranianCriterion(VisibilityCriterion):
    """Iran resmi kriteri: irtifa > 5 ve elongasyon > 10"""

    @property
    def name(self):
        return "iranian"

    def score(self, alt_deg, elong_deg, age_hours=None):
        return min(alt_deg - 5.0, elong_deg - 10.0)

    def is_visible(self, alt_deg, elong_deg, age_hours=None):
        return alt_deg > 5.0 and elong_deg > 10.0

    def description(self, q):
        if q >= 0:
            return "Iran kriterine gore gorunur"
        else:
            return "Iran kriterine gore gorunmez"


CRITERIA = {
    "odeh":     OdehCriterion(),
    "yallop":   YallopCriterion(),
    "iranian":  IranianCriterion(),
}

DEFAULT_CRITERION = "odeh"


def get_criterion(name):
    return CRITERIA.get(name.lower(), CRITERIA[DEFAULT_CRITERION])
