from typing import Tuple, List

import apimoex
import pandas as pd
from requests import Session


def get_securities() -> Tuple[pd.DataFrame, List[str]]:
    try:
        with Session() as session:
            iss = apimoex.ISSClient(session,
                                    'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json',
                                    {'securities.columns': 'SECID,SHORTNAME'})
            securities = pd.DataFrame(iss.get()['securities'])
        return securities, list(securities['SHORTNAME'])
    except Exception:
        return pd.DataFrame(), []
