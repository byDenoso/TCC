from cobaya.likelihoods.base_classes import PlanckPlikLite


class PlanckFullLite(PlanckPlikLite):
    """Native full Planck 2018 PlikLite TT/TE/EE likelihood.

    Uses the same plik_lite_v22.dataset payload as PlanckActCut, but without
    multipole cuts. This avoids any clik binary dependency in the overlap lane.
    """

    path = None
    dataset_file = "plik_lite_v22.dataset"
    aliases = ["plikHM_TTTEEE"]
    speed = 200
    params = {
        "A_planck": {
            "prior": {"dist": "norm", "loc": 1, "scale": 0.0025},
            "ref": {"dist": "norm", "loc": 1, "scale": 0.002},
            "proposal": 0.0005,
            "latex": "y_\\mathrm{cal}",
            "renames": "calPlanck",
        }
    }
