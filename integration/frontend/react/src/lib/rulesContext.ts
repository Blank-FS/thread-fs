import { createContext, useContext } from "react";

// Where the community's comment rules are (its rules_url, set by its admins), for every comment box in the
// widget: the top one, and the reply and edit boxes inside comments. Null for none.
export const RulesUrlContext = createContext<string | null>(null);

export const useRulesUrl = () => useContext(RulesUrlContext);
