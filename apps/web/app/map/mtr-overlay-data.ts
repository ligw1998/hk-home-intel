export type MtrStation = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  exitCount: number;
  lineIds: string[];
};

export type MtrLine = {
  id: string;
  name: string;
  color: string;
  stationNames: string[];
};

export type MtrAccessPoint = {
  id: string;
  stationName: string;
  label: string;
  lat: number;
  lng: number;
  station: MtrStation;
};

export type NearestMtrStation = {
  station: MtrStation;
  accessPoint: MtrAccessPoint | null;
  distanceMeters: number;
};

type StationSeed = {
  name: string;
  lat: number;
  lng: number;
  exitCount: number;
};

const MTR_STATION_SEEDS: StationSeed[] = [
  { name: "Admiralty", lat: 22.27942, lng: 114.16435, exitCount: 7 },
  { name: "Airport", lat: 22.31592, lng: 113.93648, exitCount: 5 },
  { name: "AsiaWorld-Expo", lat: 22.32175, lng: 113.94124, exitCount: 2 },
  { name: "Austin", lat: 22.30491, lng: 114.16632, exitCount: 13 },
  { name: "Causeway Bay", lat: 22.28019, lng: 114.18424, exitCount: 11 },
  { name: "Central", lat: 22.28215, lng: 114.15768, exitCount: 14 },
  { name: "Chai Wan", lat: 22.26458, lng: 114.23711, exitCount: 5 },
  { name: "Che Kung Temple", lat: 22.37477, lng: 114.18589, exitCount: 6 },
  { name: "Cheung Sha Wan", lat: 22.33555, lng: 114.15605, exitCount: 7 },
  { name: "Choi Hung", lat: 22.33497, lng: 114.20904, exitCount: 8 },
  { name: "City One", lat: 22.38296, lng: 114.20363, exitCount: 4 },
  { name: "Diamond Hill", lat: 22.34003, lng: 114.20165, exitCount: 6 },
  { name: "Disneyland Resort", lat: 22.31549, lng: 114.04485, exitCount: 1 },
  { name: "East Tsim Sha Tsui", lat: 22.29531, lng: 114.17465, exitCount: 16 },
  { name: "Exhibition Centre", lat: 22.28166, lng: 114.17532, exitCount: 6 },
  { name: "Fanling", lat: 22.4921, lng: 114.13867, exitCount: 5 },
  { name: "Fo Tan", lat: 22.39582, lng: 114.1985, exitCount: 4 },
  { name: "Fortress Hill", lat: 22.28791, lng: 114.19359, exitCount: 2 },
  { name: "HKU", lat: 22.28405, lng: 114.13556, exitCount: 6 },
  { name: "Hang Hau", lat: 22.31574, lng: 114.26431, exitCount: 4 },
  { name: "Heng Fa Chuen", lat: 22.27664, lng: 114.23971, exitCount: 2 },
  { name: "Heng On", lat: 22.41786, lng: 114.22588, exitCount: 3 },
  { name: "Hin Keng", lat: 22.36373, lng: 114.17074, exitCount: 1 },
  { name: "Ho Man Tin", lat: 22.30939, lng: 114.18259, exitCount: 7 },
  { name: "Hong Kong", lat: 22.28467, lng: 114.15822, exitCount: 7 },
  { name: "Hung Hom", lat: 22.30299, lng: 114.18219, exitCount: 14 },
  { name: "Jordan", lat: 22.30481, lng: 114.17165, exitCount: 7 },
  { name: "Kai Tak", lat: 22.33042, lng: 114.19935, exitCount: 7 },
  { name: "Kam Sheung Road", lat: 22.43513, lng: 114.06318, exitCount: 4 },
  { name: "Kennedy Town", lat: 22.28121, lng: 114.1284, exitCount: 3 },
  { name: "Kowloon", lat: 22.30426, lng: 114.16144, exitCount: 12 },
  { name: "Kowloon Bay", lat: 22.32346, lng: 114.214, exitCount: 3 },
  { name: "Kowloon Tong", lat: 22.33712, lng: 114.17578, exitCount: 11 },
  { name: "Kwai Fong", lat: 22.3568, lng: 114.12779, exitCount: 5 },
  { name: "Kwai Hing", lat: 22.36307, lng: 114.13122, exitCount: 5 },
  { name: "Kwun Tong", lat: 22.31209, lng: 114.2265, exitCount: 16 },
  { name: "LOHAS Park", lat: 22.29559, lng: 114.26873, exitCount: 3 },
  { name: "Lai Chi Kok", lat: 22.33725, lng: 114.14796, exitCount: 8 },
  { name: "Lai King", lat: 22.34834, lng: 114.12619, exitCount: 5 },
  { name: "Lam Tin", lat: 22.30683, lng: 114.23274, exitCount: 5 },
  { name: "Lei Tung", lat: 22.24185, lng: 114.156, exitCount: 3 },
  { name: "Lo Wu", lat: 22.52764, lng: 114.11323, exitCount: 0 },
  { name: "Lok Fu", lat: 22.33801, lng: 114.18703, exitCount: 2 },
  { name: "Lok Ma Chau", lat: 22.51447, lng: 114.06569, exitCount: 0 },
  { name: "Long Ping", lat: 22.44763, lng: 114.02545, exitCount: 7 },
  { name: "Ma On Shan", lat: 22.42491, lng: 114.23198, exitCount: 3 },
  { name: "Mei Foo", lat: 22.33793, lng: 114.13639, exitCount: 8 },
  { name: "Mong Kok", lat: 22.3193, lng: 114.16935, exitCount: 15 },
  { name: "Mong Kok East", lat: 22.32202, lng: 114.17259, exitCount: 4 },
  { name: "Nam Cheong", lat: 22.32688, lng: 114.1535, exitCount: 6 },
  { name: "Ngau Tau Kok", lat: 22.3155, lng: 114.21898, exitCount: 8 },
  { name: "North Point", lat: 22.29118, lng: 114.20039, exitCount: 9 },
  { name: "Ocean Park", lat: 22.24871, lng: 114.17432, exitCount: 3 },
  { name: "Olympic", lat: 22.31779, lng: 114.16025, exitCount: 12 },
  { name: "Po Lam", lat: 22.32256, lng: 114.25787, exitCount: 6 },
  { name: "Prince Edward", lat: 22.32441, lng: 114.16828, exitCount: 7 },
  { name: "Quarry Bay", lat: 22.28857, lng: 114.2087, exitCount: 3 },
  { name: "Racecourse", lat: 22.40019, lng: 114.20278, exitCount: 3 },
  { name: "Sai Wan Ho", lat: 22.28218, lng: 114.22182, exitCount: 2 },
  { name: "Sai Ying Pun", lat: 22.28551, lng: 114.1427, exitCount: 6 },
  { name: "Sha Tin", lat: 22.38213, lng: 114.18691, exitCount: 5 },
  { name: "Sha Tin Wai", lat: 22.37691, lng: 114.19481, exitCount: 4 },
  { name: "Sham Shui Po", lat: 22.33089, lng: 114.16212, exitCount: 8 },
  { name: "Shau Kei Wan", lat: 22.27923, lng: 114.22895, exitCount: 9 },
  { name: "Shek Kip Mei", lat: 22.33179, lng: 114.16882, exitCount: 5 },
  { name: "Shek Mun", lat: 22.38788, lng: 114.20852, exitCount: 4 },
  { name: "Sheung Shui", lat: 22.50162, lng: 114.12753, exitCount: 11 },
  { name: "Sheung Wan", lat: 22.2866, lng: 114.15201, exitCount: 10 },
  { name: "Siu Hong", lat: 22.41153, lng: 113.9788, exitCount: 9 },
  { name: "South Horizons", lat: 22.24285, lng: 114.14885, exitCount: 3 },
  { name: "Sung Wong Toi", lat: 22.32563, lng: 114.19062, exitCount: 5 },
  { name: "Sunny Bay", lat: 22.33211, lng: 114.02904, exitCount: 1 },
  { name: "Tai Koo", lat: 22.28465, lng: 114.21648, exitCount: 9 },
  { name: "Tai Po Market", lat: 22.44458, lng: 114.17039, exitCount: 4 },
  { name: "Tai Shui Hang", lat: 22.40819, lng: 114.2226, exitCount: 2 },
  { name: "Tai Wai", lat: 22.37276, lng: 114.17869, exitCount: 8 },
  { name: "Tai Wo", lat: 22.45107, lng: 114.16118, exitCount: 2 },
  { name: "Tai Wo Hau", lat: 22.37076, lng: 114.12501, exitCount: 3 },
  { name: "Tin Hau", lat: 22.28224, lng: 114.19185, exitCount: 3 },
  { name: "Tin Shui Wai", lat: 22.44788, lng: 114.00447, exitCount: 7 },
  { name: "Tiu Keng Leng", lat: 22.30426, lng: 114.25264, exitCount: 3 },
  { name: "To Kwa Wan", lat: 22.31792, lng: 114.18762, exitCount: 4 },
  { name: "Tseung Kwan O", lat: 22.30744, lng: 114.26001, exitCount: 5 },
  { name: "Tsim Sha Tsui", lat: 22.2977, lng: 114.17218, exitCount: 12 },
  { name: "Tsing Yi", lat: 22.3584, lng: 114.10728, exitCount: 6 },
  { name: "Tsuen Wan", lat: 22.37352, lng: 114.11808, exitCount: 11 },
  { name: "Tsuen Wan West", lat: 22.36839, lng: 114.10966, exitCount: 12 },
  { name: "Tuen Mun", lat: 22.39511, lng: 113.97319, exitCount: 9 },
  { name: "Tung Chung", lat: 22.28918, lng: 113.94127, exitCount: 4 },
  { name: "University", lat: 22.41366, lng: 114.21004, exitCount: 4 },
  { name: "Wan Chai", lat: 22.27755, lng: 114.17263, exitCount: 9 },
  { name: "Whampoa", lat: 22.30481, lng: 114.18983, exitCount: 7 },
  { name: "Wong Chuk Hang", lat: 22.24798, lng: 114.168, exitCount: 4 },
  { name: "Wong Tai Sin", lat: 22.34168, lng: 114.19387, exitCount: 10 },
  { name: "Wu Kai Sha", lat: 22.42915, lng: 114.24385, exitCount: 3 },
  { name: "Yau Ma Tei", lat: 22.31283, lng: 114.17066, exitCount: 7 },
  { name: "Yau Tong", lat: 22.298, lng: 114.237, exitCount: 4 },
  { name: "Yuen Long", lat: 22.44607, lng: 114.03517, exitCount: 10 },
];

const MTR_ACCESS_POINT_ROWS = `Admiralty|C2|22.279|114.16485;Admiralty|D|22.27872|114.16562;Admiralty|E|22.27894|114.16607;Admiralty|C1|22.27854|114.16477;Admiralty|B|22.27939|114.16403;Admiralty|F|22.27859|114.16608;Admiralty|A|22.27952|114.16508;Airport|D|22.31497|113.93667;Airport|C|22.31644|113.93608;Airport|A|22.31524|113.93653;Airport|B|22.31584|113.93631;Airport|E|22.31674|113.93602;AsiaWorld-Expo|A|22.32225|113.94371;AsiaWorld-Expo|B|22.32162|113.94078;Austin|B2|22.30509|114.16606;Austin|B3|22.3052|114.16634;Austin|E|22.30314|114.16707;Austin|D1|22.30373|114.16672;Austin|B4|22.30539|114.16591;Austin|B5|22.30586|114.16579;Austin|F|22.30315|114.16758;Austin|D2|22.30342|114.16674;Austin|A|22.30591|114.16635;Austin|B1|22.30532|114.16594;Austin|C|22.30425|114.16649;Austin|D3|22.3036|114.1671;Austin|D4|22.30381|114.16671;Causeway Bay|B|22.28017|114.18285;Causeway Bay|Access|22.28064|114.1845;Causeway Bay|A|22.27854|114.1825;Causeway Bay|C|22.28049|114.18279;Causeway Bay|E|22.28039|114.18506;Causeway Bay|F2|22.27989|114.18411;Causeway Bay|D2|22.28029|114.18422;Causeway Bay|D1|22.28058|114.18426;Causeway Bay|F1|22.27985|114.18434;Causeway Bay|D4|22.28042|114.18425;Causeway Bay|D3|22.28046|114.18432;Central|D1|22.28181|114.15722;Central|J2|22.28104|114.16091;Central|D2|22.28196|114.1571;Central|J3|22.28128|114.16088;Central|K|22.28118|114.15957;Central|E|22.28198|114.15816;Central|F|22.28186|114.1586;Central|G|22.28177|114.15765;Central|B|22.2825|114.15761;Central|H|22.28164|114.15875;Central|C|22.2822|114.15742;Central|A|22.28277|114.15788;Central|J1|22.28123|114.16057;Central|L|22.28134|114.16139;Chai Wan|A|22.26384|114.23682;Chai Wan|D|22.2654|114.23745;Chai Wan|B|22.26412|114.23679;Chai Wan|C|22.26494|114.23722;Chai Wan|E|22.2639|114.23667;Che Kung Temple|D|22.37464|114.18632;Che Kung Temple|C|22.37486|114.18634;Che Kung Temple|E|22.37485|114.18658;Che Kung Temple|A|22.37489|114.18578;Che Kung Temple|B|22.37466|114.18576;Che Kung Temple|F|22.37483|114.18695;Cheung Sha Wan|C1|22.3356|114.15648;Cheung Sha Wan|A|22.33516|114.15682;Cheung Sha Wan|A1|22.33431|114.15722;Cheung Sha Wan|C2|22.33649|114.15512;Cheung Sha Wan|A2|22.33491|114.15778;Cheung Sha Wan|A3|22.3349|114.15717;Cheung Sha Wan|B|22.33576|114.15539;Choi Hung|C2|22.33565|114.20787;Choi Hung|A3|22.33405|114.2097;Choi Hung|B|22.33436|114.20935;Choi Hung|A1|22.33407|114.20964;Choi Hung|C1|22.3349|114.2082;Choi Hung|C3|22.33485|114.20781;Choi Hung|C4|22.33546|114.2075;Choi Hung|A2|22.33401|114.20935;City One|A|22.38252|114.20309;City One|C|22.38315|114.20375;City One|B|22.38245|114.20316;City One|D|22.38309|114.20383;Diamond Hill|B|22.33936|114.20205;Diamond Hill|C2|22.34026|114.20245;Diamond Hill|C1|22.34016|114.20227;Diamond Hill|A1|22.34101|114.20087;Diamond Hill|Access|22.34082|114.20084;Diamond Hill|A2|22.34004|114.20034;Disneyland Resort|A|22.31521|114.04539;East Tsim Sha Tsui|L3|22.29565|114.17205;East Tsim Sha Tsui|L5|22.29614|114.17046;East Tsim Sha Tsui|Access|22.29561|114.17145;East Tsim Sha Tsui|L6|22.29511|114.1707;East Tsim Sha Tsui|N5|22.29703|114.17263;East Tsim Sha Tsui|L4|22.29567|114.17175;East Tsim Sha Tsui|P1|22.29698|114.17613;East Tsim Sha Tsui|P2|22.29731|114.17619;East Tsim Sha Tsui|N3|22.29733|114.1743;East Tsim Sha Tsui|J|22.29505|114.17369;East Tsim Sha Tsui|N4|22.29723|114.17372;East Tsim Sha Tsui|L1|22.29577|114.17313;East Tsim Sha Tsui|P3|22.29723|114.17536;East Tsim Sha Tsui|N1|22.29743|114.1744;East Tsim Sha Tsui|N2|22.29777|114.174;East Tsim Sha Tsui|K|22.29548|114.17373;Exhibition Centre|B3|22.28123|114.17458;Exhibition Centre|A3|22.28133|114.17586;Exhibition Centre|A2|22.28156|114.17625;Exhibition Centre|A1|22.28136|114.17624;Exhibition Centre|B2|22.28158|114.17493;Exhibition Centre|B1|22.28144|114.17488;Fanling|A2|22.49185|114.13915;Fanling|A1|22.49199|114.13901;Fanling|B|22.49182|114.1388;Fanling|A3|22.49202|114.13899;Fanling|C|22.4926|114.13837;Fo Tan|A|22.39473|114.19799;Fo Tan|D|22.39585|114.19841;Fo Tan|C|22.39572|114.19865;Fo Tan|B|22.39485|114.19775;Fortress Hill|A|22.28809|114.19365;Fortress Hill|B|22.28841|114.19396;HKU|B2|22.28562|114.13514;HKU|B1|22.28567|114.13683;HKU|C1|22.28449|114.13456;HKU|C2|22.28586|114.13263;HKU|A1|22.28347|114.13669;HKU|A2|22.28347|114.13669;Hang Hau|B2|22.31519|114.26443;Hang Hau|A2|22.31588|114.26393;Hang Hau|B1|22.31518|114.26467;Hang Hau|A1|22.31605|114.26415;Heng Fa Chuen|A1|22.27706|114.2398;Heng Fa Chuen|A2|22.27656|114.24021;Heng On|B|22.41779|114.22593;Heng On|A|22.41782|114.2258;Heng On|C|22.41841|114.22609;Hin Keng|A|22.36367|114.17091;Ho Man Tin|A1|22.31033|114.1834;Ho Man Tin|A2|22.31135|114.18353;Ho Man Tin|B1|22.30925|114.18294;Ho Man Tin|B2|22.30896|114.18229;Ho Man Tin|A3|22.31039|114.18218;Ho Man Tin|C|22.30976|114.18297;Ho Man Tin|A4|22.31063|114.18327;Hong Kong|E|22.28508|114.15724;Hong Kong|A|22.28434|114.15828;Hong Kong|B2|22.28413|114.15901;Hong Kong|C|22.28316|114.15714;Hong Kong|F|22.28527|114.15848;Hong Kong|D|22.28492|114.15735;Hong Kong|B1|22.2841|114.15875;Hung Hom|C1|22.30337|114.18241;Hung Hom|A3|22.30411|114.18148;Hung Hom|B2|22.30354|114.18222;Hung Hom|A1|22.30346|114.18117;Hung Hom|C2|22.30284|114.18235;Hung Hom|D4|22.30077|114.1811;Hung Hom|D3|22.30136|114.18122;Hung Hom|A2|22.30383|114.18145;Hung Hom|C3|22.3023|114.18229;Hung Hom|D1|22.30206|114.18101;Hung Hom|D2|22.30187|114.18208;Hung Hom|D5|22.30074|114.18094;Hung Hom|B1|22.30409|114.18315;Hung Hom|D6|22.30216|114.18131;Jordan|C1|22.30433|114.17148;Jordan|C2|22.30431|114.17118;Jordan|D|22.30378|114.17191;Jordan|E|22.3043|114.17197;Jordan|A|22.30542|114.17128;Jordan|B2|22.30571|114.17224;Jordan|B1|22.30552|114.17186;Kai Tak|D|22.32979|114.19883;Kai Tak|C|22.33094|114.19866;Kai Tak|B1|22.33151|114.19979;Kai Tak|Access|22.33085|114.20038;Kai Tak|Access|22.33|114.19882;Kai Tak|A|22.33084|114.20053;Kai Tak|B2|22.33126|114.19952;Kam Sheung Road|A|22.43541|114.06288;Kam Sheung Road|D|22.43417|114.06373;Kam Sheung Road|B|22.4355|114.06307;Kam Sheung Road|C|22.4343|114.06394;Kennedy Town|A|22.28113|114.12856;Kennedy Town|C|22.28125|114.12804;Kennedy Town|B|22.28207|114.12928;Kowloon|E4|22.30534|114.16107;Kowloon|C1|22.3048|114.16193;Kowloon|D1|22.30507|114.16121;Kowloon|A|22.30562|114.16223;Kowloon|E2|22.30476|114.16078;Kowloon|E1|22.3045|114.16068;Kowloon|D2|22.30497|114.16146;Kowloon|E6|22.30581|114.16127;Kowloon|B|22.30407|114.16135;Kowloon|E5|22.30556|114.16115;Kowloon|C2|22.30489|114.16168;Kowloon|E3|22.30494|114.16089;Kowloon Bay|B|22.32446|114.21398;Kowloon Bay|A|22.32262|114.21416;Kowloon Bay|C|22.32365|114.21404;Kowloon Tong|G2|22.33715|114.17595;Kowloon Tong|F|22.33709|114.17621;Kowloon Tong|C1|22.33701|114.1754;Kowloon Tong|G1|22.33707|114.17602;Kowloon Tong|A2|22.33689|114.17824;Kowloon Tong|C2|22.33672|114.17558;Kowloon Tong|D|22.33647|114.17652;Kowloon Tong|E|22.33667|114.17751;Kowloon Tong|A1|22.33691|114.17784;Kowloon Tong|H|22.33727|114.17543;Kowloon Tong|B|22.33698|114.17654;Kwai Fong|E|22.3571|114.12789;Kwai Fong|B|22.35627|114.12748;Kwai Fong|A|22.35726|114.12823;Kwai Fong|C|22.35637|114.12734;Kwai Fong|D|22.35736|114.12808;Kwai Hing|D|22.3636|114.13114;Kwai Hing|B|22.36276|114.13124;Kwai Hing|C|22.36261|114.1311;Kwai Hing|E|22.36267|114.13129;Kwai Hing|A|22.36374|114.13128;Kwun Tong|B|22.31209|114.22633;Kwun Tong|C|22.31237|114.2265;Kwun Tong|A1|22.31276|114.2258;Kwun Tong|C3|22.31274|114.22605;Kwun Tong|B2|22.31151|114.22615;Kwun Tong|D3|22.31165|114.22701;Kwun Tong|C1|22.31244|114.22688;Kwun Tong|A2|22.3124|114.22562;Kwun Tong|C2|22.31228|114.22688;Kwun Tong|D2|22.31189|114.22734;Kwun Tong|B1|22.31157|114.22621;Kwun Tong|D|22.31168|114.22725;Kwun Tong|A|22.31259|114.22571;Kwun Tong|B3|22.31178|114.22604;Kwun Tong|D4|22.31145|114.22729;Kwun Tong|D1|22.31178|114.22752;LOHAS Park|C2|22.29619|114.26958;LOHAS Park|C1|22.29626|114.26969;LOHAS Park|B|22.29534|114.26838;Lai Chi Kok|A|22.33733|114.14891;Lai Chi Kok|B2|22.33755|114.14838;Lai Chi Kok|C|22.33701|114.14681;Lai Chi Kok|B1|22.33778|114.14905;Lai Chi Kok|D2|22.33623|114.14821;Lai Chi Kok|D1|22.3364|114.14815;Lai Chi Kok|D3|22.33553|114.14899;Lai Chi Kok|D4|22.33549|114.14932;Lai King|B|22.34848|114.12582;Lai King|A3|22.34792|114.12625;Lai King|C|22.34884|114.12606;Lai King|A1|22.348|114.12652;Lai King|A2|22.34833|114.12645;Lam Tin|D2|22.30723|114.23202;Lam Tin|A|22.308|114.2343;Lam Tin|D1|22.30708|114.23182;Lam Tin|C|22.30602|114.23362;Lam Tin|B|22.3069|114.23352;Lei Tung|A1|22.24364|114.15535;Lei Tung|A2|22.24356|114.15541;Lei Tung|B|22.24098|114.15615;Lok Fu|B|22.33778|114.18777;Lok Fu|A|22.33822|114.18768;Long Ping|D|22.44757|114.02594;Long Ping|B2|22.44753|114.0235;Long Ping|A|22.44774|114.02438;Long Ping|E|22.44756|114.02647;Long Ping|C|22.44757|114.02489;Long Ping|B1|22.44752|114.02466;Long Ping|F|22.44779|114.02649;Ma On Shan|A2|22.42519|114.23168;Ma On Shan|B|22.42471|114.23156;Ma On Shan|A1|22.42506|114.23124;Mei Foo|A|22.33668|114.14026;Mei Foo|D|22.33794|114.13772;Mei Foo|F|22.33854|114.13682;Mei Foo|C1|22.33838|114.13835;Mei Foo|B|22.33768|114.13985;Mei Foo|G|22.33968|114.13646;Mei Foo|C2|22.33821|114.13871;Mei Foo|E|22.33823|114.13861;Mong Kok|C3|22.31862|114.16864;Mong Kok|B2|22.32039|114.16966;Mong Kok|E2|22.31842|114.16978;Mong Kok|A1|22.32025|114.16897;Mong Kok|C4|22.31913|114.16884;Mong Kok|B3|22.32057|114.1697;Mong Kok|D2|22.31946|114.16981;Mong Kok|E1|22.31833|114.16933;Mong Kok|C2|22.3193|114.16888;Mong Kok|B4|22.32051|114.16948;Mong Kok|D3|22.31921|114.17006;Mong Kok|B1|22.32034|114.16938;Mong Kok|A2|22.32019|114.16867;Mong Kok|C1|22.31935|114.16914;Mong Kok|D1|22.31942|114.16959;Mong Kok East|A|22.32169|114.17265;Mong Kok East|D|22.32265|114.17266;Mong Kok East|B|22.3217|114.17249;Mong Kok East|C|22.3226|114.17254;Nam Cheong|B|22.32625|114.15267;Nam Cheong|D1|22.32572|114.15524;Nam Cheong|A2|22.32774|114.15359;Nam Cheong|C|22.325|114.15427;Nam Cheong|A1|22.32791|114.1536;Nam Cheong|D2|22.32637|114.15452;Ngau Tau Kok|A|22.31552|114.21938;Ngau Tau Kok|B2|22.31595|114.21919;Ngau Tau Kok|B6|22.31497|114.21847;Ngau Tau Kok|B3|22.31604|114.21876;Ngau Tau Kok|B4|22.31586|114.21858;Ngau Tau Kok|B|22.31564|114.21905;Ngau Tau Kok|B5|22.31506|114.21875;Ngau Tau Kok|B1|22.31576|114.21947;North Point|A3|22.29204|114.20027;North Point|B2|22.29104|114.20068;North Point|B4|22.29071|114.2007;North Point|B1|22.29105|114.20046;North Point|Access|22.29094|114.20043;North Point|A1|22.29222|114.20028;North Point|A2|22.29191|114.20027;North Point|B3|22.29112|114.20087;North Point|A4|22.29162|114.20031;Ocean Park|C|22.249|114.17487;Ocean Park|A|22.24834|114.17389;Ocean Park|B|22.24812|114.17451;Olympic|C3|22.31812|114.16072;Olympic|A2|22.31816|114.15914;Olympic|C2|22.31806|114.16101;Olympic|D1|22.31704|114.16125;Olympic|C5|22.31818|114.16131;Olympic|B|22.31865|114.16056;Olympic|C1|22.31834|114.16068;Olympic|C4|22.31812|114.16103;Olympic|D2|22.31673|114.16116;Olympic|E|22.31786|114.15916;Olympic|D3|22.31691|114.16112;Olympic|A1|22.31821|114.15914;Po Lam|B1|22.32207|114.25834;Po Lam|A1|22.32292|114.25742;Po Lam|C|22.32248|114.25776;Po Lam|A2|22.32305|114.25757;Po Lam|B3|22.32181|114.2583;Po Lam|B2|22.32185|114.25824;Prince Edward|B1|22.32416|114.16859;Prince Edward|B2|22.32388|114.16902;Prince Edward|C1|22.32407|114.16821;Prince Edward|C2|22.32404|114.16803;Prince Edward|D|22.3251|114.16768;Prince Edward|A|22.32507|114.16837;Prince Edward|E|22.32515|114.16796;Quarry Bay|A|22.28778|114.20993;Quarry Bay|B|22.28847|114.21037;Quarry Bay|C|22.29057|114.20792;Racecourse|B|22.4004|114.20285;Racecourse|A|22.39952|114.2023;Racecourse|C|22.40113|114.20337;Sai Wan Ho|B|22.28199|114.22219;Sai Wan Ho|A|22.28226|114.22245;Sai Ying Pun|A2|22.28773|114.14423;Sai Ying Pun|B2|22.28626|114.14178;Sai Ying Pun|A1|22.28713|114.14444;Sai Ying Pun|B3|22.28758|114.14151;Sai Ying Pun|B1|22.28648|114.14174;Sai Ying Pun|C|22.28457|114.14335;Sha Tin|A1|22.38285|114.18778;Sha Tin|A3|22.38241|114.18754;Sha Tin|A4|22.38221|114.18731;Sha Tin|B|22.38294|114.18763;Sha Tin|A2|22.38268|114.18773;Sha Tin Wai|A|22.37682|114.19464;Sha Tin Wai|C|22.37736|114.19539;Sha Tin Wai|D|22.37731|114.19544;Sha Tin Wai|B|22.37677|114.19468;Sham Shui Po|D1|22.33117|114.16204;Sham Shui Po|D2|22.33146|114.16224;Sham Shui Po|C2|22.33066|114.16157;Sham Shui Po|A2|22.32999|114.16245;Sham Shui Po|B2|22.33079|114.16311;Sham Shui Po|B1|22.33049|114.1629;Sham Shui Po|C1|22.33095|114.16176;Sham Shui Po|A1|22.33028|114.16264;Shau Kei Wan|D2|22.27975|114.22893;Shau Kei Wan|A1|22.27896|114.2288;Shau Kei Wan|B1|22.27919|114.22968;Shau Kei Wan|D1|22.28042|114.22982;Shau Kei Wan|B2|22.27981|114.22987;Shau Kei Wan|A2|22.27871|114.22867;Shau Kei Wan|B3|22.27954|114.22824;Shau Kei Wan|A3|22.27867|114.22825;Shau Kei Wan|C|22.27883|114.22974;Shek Kip Mei|C|22.33275|114.16883;Shek Kip Mei|B2|22.3317|114.16899;Shek Kip Mei|B1|22.33147|114.16914;Shek Kip Mei|Access|22.33146|114.16868;Shek Kip Mei|A|22.33168|114.16856;Shek Mun|B|22.38739|114.20813;Shek Mun|D|22.38796|114.20869;Shek Mun|C|22.38803|114.20863;Shek Mun|A|22.38746|114.20805;Sheung Shui|B2|22.50098|114.12846;Sheung Shui|B1|22.50079|114.12827;Sheung Shui|A1|22.50137|114.12761;Sheung Shui|A3|22.50168|114.12762;Sheung Shui|D2|22.50146|114.12791;Sheung Shui|D1|22.50169|114.12769;Sheung Shui|A4|22.50155|114.12779;Sheung Shui|A2|22.5016|114.12729;Sheung Shui|D3|22.5015|114.12785;Sheung Shui|C|22.50138|114.12748;Sheung Shui|E|22.50107|114.12836;Sheung Wan|E2|22.28589|114.1533;Sheung Wan|E5|22.28658|114.15363;Sheung Wan|C|22.28704|114.15214;Sheung Wan|E3|22.28619|114.15364;Sheung Wan|E1|22.28606|114.15334;Sheung Wan|B|22.28669|114.15204;Sheung Wan|D|22.28762|114.15215;Sheung Wan|A1|22.28635|114.15226;Sheung Wan|A2|22.28614|114.15221;Sheung Wan|E4|22.28662|114.15367;Siu Hong|B1|22.41177|113.97867;Siu Hong|C3|22.41217|113.97838;Siu Hong|A|22.41098|113.9786;Siu Hong|F|22.41205|113.97918;Siu Hong|C1|22.41183|113.97826;Siu Hong|E|22.41273|113.9791;Siu Hong|C2|22.41204|113.97815;Siu Hong|B2|22.41203|113.97874;Siu Hong|D|22.41191|113.97863;South Horizons|C|22.24275|114.14902;South Horizons|A|22.24347|114.14893;South Horizons|B|22.24294|114.1482;Sung Wong Toi|A|22.32615|114.19193;Sung Wong Toi|D|22.32564|114.1912;Sung Wong Toi|B3|22.32854|114.18986;Sung Wong Toi|B2|22.32804|114.18984;Sung Wong Toi|B1|22.32698|114.1897;Sunny Bay|A|22.33194|114.02867;Tai Koo|E1|22.28551|114.21722;Tai Koo|D1|22.28593|114.21665;Tai Koo|D2|22.28587|114.21681;Tai Koo|B|22.28446|114.21503;Tai Koo|E2|22.28532|114.21693;Tai Koo|A2|22.28484|114.21549;Tai Koo|A1|22.28507|114.2152;Tai Koo|C|22.28442|114.21683;Tai Koo|E3|22.28535|114.21688;Tai Po Market|A1|22.44425|114.16996;Tai Po Market|A3|22.44424|114.17008;Tai Po Market|A2|22.44437|114.16976;Tai Po Market|B|22.44421|114.17111;Tai Shui Hang|A|22.40769|114.22229;Tai Shui Hang|B|22.40765|114.22238;Tai Wai|F|22.37215|114.17783;Tai Wai|D|22.37313|114.17826;Tai Wai|G|22.37237|114.17721;Tai Wai|E|22.37259|114.17752;Tai Wai|C|22.37272|114.17802;Tai Wai|B|22.373|114.17937;Tai Wai|A|22.37352|114.1789;Tai Wai|H|22.37337|114.17952;Tai Wo|B|22.45113|114.16144;Tai Wo|A|22.45092|114.16114;Tai Wo Hau|A|22.37099|114.1259;Tai Wo Hau|B|22.37064|114.12437;Tai Wo Hau|Access|22.37065|114.12473;Tin Hau|B|22.28239|114.19174;Tin Hau|A1|22.28292|114.19209;Tin Hau|A2|22.28291|114.19177;Tin Shui Wai|E3|22.44906|114.00583;Tin Shui Wai|E1|22.44926|114.00562;Tin Shui Wai|A|22.44681|114.00357;Tin Shui Wai|E2|22.44917|114.00572;Tin Shui Wai|B|22.44697|114.00342;Tin Shui Wai|D|22.44908|114.00544;Tin Shui Wai|C|22.4481|114.00452;Tiu Keng Leng|A1|22.30447|114.25272;Tiu Keng Leng|A2|22.30433|114.25287;Tiu Keng Leng|B|22.30409|114.25232;To Kwa Wan|B|22.31793|114.18711;To Kwa Wan|C|22.31628|114.18715;To Kwa Wan|D|22.31532|114.18786;To Kwa Wan|A|22.31781|114.18791;Tseung Kwan O|A1|22.30774|114.26075;Tseung Kwan O|A2|22.30757|114.2608;Tseung Kwan O|B1|22.30701|114.25916;Tseung Kwan O|B2|22.30719|114.25908;Tseung Kwan O|C|22.30754|114.25988;Tsim Sha Tsui|H|22.29661|114.17203;Tsim Sha Tsui|A1|22.29831|114.17188;Tsim Sha Tsui|C1|22.29687|114.17212;Tsim Sha Tsui|A2|22.29819|114.17242;Tsim Sha Tsui|D3|22.2976|114.17303;Tsim Sha Tsui|B1|22.29875|114.1723;Tsim Sha Tsui|D1|22.29764|114.17237;Tsim Sha Tsui|B2|22.29876|114.17255;Tsim Sha Tsui|R|22.29729|114.172;Tsim Sha Tsui|E|22.29619|114.17215;Tsim Sha Tsui|C2|22.29721|114.1721;Tsim Sha Tsui|D2|22.29766|114.1727;Tsing Yi|F|22.35849|114.1077;Tsing Yi|A2|22.3589|114.10773;Tsing Yi|A1|22.35926|114.10717;Tsing Yi|B|22.3579|114.10737;Tsing Yi|G|22.35844|114.10766;Tsing Yi|C|22.35773|114.10711;Tsuen Wan|D|22.3738|114.11726;Tsuen Wan|A3|22.37409|114.11609;Tsuen Wan|B2|22.37301|114.11854;Tsuen Wan|B1|22.37314|114.11825;Tsuen Wan|A|22.37405|114.11677;Tsuen Wan|C|22.37343|114.11853;Tsuen Wan|A4|22.37413|114.11655;Tsuen Wan|A2|22.37388|114.11662;Tsuen Wan|A1|22.37378|114.11692;Tsuen Wan|E|22.37334|114.11829;Tsuen Wan|B3|22.37318|114.11862;Tsuen Wan West|C1|22.36753|114.11017;Tsuen Wan West|E1|22.36778|114.11082;Tsuen Wan West|C2|22.36773|114.11009;Tsuen Wan West|B1|22.3685|114.10887;Tsuen Wan West|A2|22.36881|114.11;Tsuen Wan West|E2|22.36795|114.11085;Tsuen Wan West|D|22.36717|114.1109;Tsuen Wan West|C5|22.36753|114.11041;Tsuen Wan West|C4|22.36753|114.11032;Tsuen Wan West|C3|22.36763|114.11043;Tsuen Wan West|A1|22.36858|114.10986;Tsuen Wan West|B2|22.36838|114.10916;Tuen Mun|C1|22.39419|113.97352;Tuen Mun|C3|22.39433|113.97314;Tuen Mun|F1|22.39642|113.97327;Tuen Mun|A|22.39436|113.97272;Tuen Mun|C2|22.39444|113.97378;Tuen Mun|E|22.3962|113.9736;Tuen Mun|B|22.39409|113.97294;Tuen Mun|F2|22.39637|113.9735;Tuen Mun|D|22.39536|113.97338;Tung Chung|B|22.28899|113.94091;Tung Chung|D|22.28943|113.9418;Tung Chung|C|22.28968|113.94173;Tung Chung|A|22.28892|113.94111;University|B|22.41336|114.21031;University|A|22.41373|114.20993;University|C|22.41409|114.21005;University|D|22.4151|114.21073;Wan Chai|B2|22.27727|114.17266;Wan Chai|C|22.27805|114.17291;Wan Chai|A1|22.27803|114.17322;Wan Chai|D|22.27642|114.17248;Wan Chai|A4|22.27743|114.17328;Wan Chai|B1|22.27738|114.17267;Wan Chai|A3|22.27683|114.17335;Wan Chai|A5|22.2771|114.1733;Wan Chai|A2|22.27783|114.17325;Whampoa|C1|22.30442|114.1897;Whampoa|C2|22.30451|114.18979;Whampoa|Access|22.30481|114.1902;Whampoa|B|22.30525|114.18839;Whampoa|D1|22.30415|114.19058;Whampoa|D2|22.30406|114.19085;Whampoa|A|22.30581|114.18875;Wong Chuk Hang|A2|22.24819|114.16795;Wong Chuk Hang|A1|22.24814|114.16771;Wong Chuk Hang|C|22.24792|114.16803;Wong Chuk Hang|B|22.24774|114.16685;Wong Tai Sin|D2|22.34126|114.19467;Wong Tai Sin|D1|22.34158|114.19504;Wong Tai Sin|B1|22.34181|114.19289;Wong Tai Sin|E|22.34189|114.19464;Wong Tai Sin|B3|22.34204|114.1931;Wong Tai Sin|A|22.34189|114.19448;Wong Tai Sin|B2|22.34181|114.19343;Wong Tai Sin|C2|22.34141|114.19318;Wong Tai Sin|C1|22.34156|114.19298;Wong Tai Sin|D3|22.34129|114.1944;Wu Kai Sha|A1|22.42974|114.24375;Wu Kai Sha|A2|22.4294|114.24377;Wu Kai Sha|B|22.42906|114.24387;Yau Ma Tei|B1|22.31306|114.17042;Yau Ma Tei|A1|22.31382|114.17024;Yau Ma Tei|C|22.31179|114.17066;Yau Ma Tei|D|22.31293|114.17093;Yau Ma Tei|Access|22.31285|114.1704;Yau Ma Tei|A2|22.31391|114.17075;Yau Ma Tei|B2|22.31301|114.17013;Yau Tong|B1|22.29856|114.23674;Yau Tong|A1|22.29725|114.23771;Yau Tong|A2|22.29716|114.23756;Yau Tong|B2|22.29847|114.2366;Yuen Long|B|22.44599|114.03345;Yuen Long|F|22.44596|114.03523;Yuen Long|J|22.44627|114.03641;Yuen Long|K|22.44594|114.03649;Yuen Long|H|22.44597|114.03673;Yuen Long|E|22.44597|114.03467;Yuen Long|A|22.44622|114.03382;Yuen Long|G1|22.44621|114.03505;Yuen Long|C|22.44596|114.03384;Yuen Long|G2|22.44622|114.03523`;

export const MTR_LINES: MtrLine[] = [
  {
    id: "island",
    name: "Island Line",
    color: "#007DC5",
    stationNames: [
      "Kennedy Town",
      "HKU",
      "Sai Ying Pun",
      "Sheung Wan",
      "Central",
      "Admiralty",
      "Wan Chai",
      "Causeway Bay",
      "Tin Hau",
      "Fortress Hill",
      "North Point",
      "Quarry Bay",
      "Tai Koo",
      "Sai Wan Ho",
      "Shau Kei Wan",
      "Heng Fa Chuen",
      "Chai Wan",
    ],
  },
  {
    id: "tsuen-wan",
    name: "Tsuen Wan Line",
    color: "#E2231A",
    stationNames: [
      "Central",
      "Admiralty",
      "Tsim Sha Tsui",
      "Jordan",
      "Yau Ma Tei",
      "Mong Kok",
      "Prince Edward",
      "Sham Shui Po",
      "Cheung Sha Wan",
      "Lai Chi Kok",
      "Mei Foo",
      "Lai King",
      "Kwai Fong",
      "Kwai Hing",
      "Tai Wo Hau",
      "Tsuen Wan",
    ],
  },
  {
    id: "kwun-tong",
    name: "Kwun Tong Line",
    color: "#00A040",
    stationNames: [
      "Whampoa",
      "Ho Man Tin",
      "Yau Ma Tei",
      "Mong Kok",
      "Prince Edward",
      "Shek Kip Mei",
      "Kowloon Tong",
      "Lok Fu",
      "Wong Tai Sin",
      "Diamond Hill",
      "Choi Hung",
      "Kowloon Bay",
      "Ngau Tau Kok",
      "Kwun Tong",
      "Lam Tin",
      "Yau Tong",
      "Tiu Keng Leng",
    ],
  },
  {
    id: "tseung-kwan-o",
    name: "Tseung Kwan O Line",
    color: "#7D499D",
    stationNames: ["North Point", "Quarry Bay", "Yau Tong", "Tiu Keng Leng", "Tseung Kwan O", "Hang Hau", "Po Lam"],
  },
  {
    id: "lohas-park-branch",
    name: "Tseung Kwan O Line - LOHAS Park",
    color: "#7D499D",
    stationNames: ["Tseung Kwan O", "LOHAS Park"],
  },
  {
    id: "tung-chung",
    name: "Tung Chung Line",
    color: "#F7941D",
    stationNames: ["Hong Kong", "Kowloon", "Olympic", "Nam Cheong", "Lai King", "Tsing Yi", "Sunny Bay", "Tung Chung"],
  },
  {
    id: "airport-express",
    name: "Airport Express",
    color: "#00888A",
    stationNames: ["Hong Kong", "Kowloon", "Tsing Yi", "Airport", "AsiaWorld-Expo"],
  },
  {
    id: "disneyland-resort",
    name: "Disneyland Resort Line",
    color: "#F550A6",
    stationNames: ["Sunny Bay", "Disneyland Resort"],
  },
  {
    id: "east-rail-lo-wu",
    name: "East Rail Line - Lo Wu",
    color: "#5EB6E4",
    stationNames: [
      "Admiralty",
      "Exhibition Centre",
      "Hung Hom",
      "Mong Kok East",
      "Kowloon Tong",
      "Tai Wai",
      "Sha Tin",
      "Fo Tan",
      "Racecourse",
      "University",
      "Tai Po Market",
      "Tai Wo",
      "Fanling",
      "Sheung Shui",
      "Lo Wu",
    ],
  },
  {
    id: "east-rail-lok-ma-chau",
    name: "East Rail Line - Lok Ma Chau",
    color: "#5EB6E4",
    stationNames: ["Sheung Shui", "Lok Ma Chau"],
  },
  {
    id: "tuen-ma",
    name: "Tuen Ma Line",
    color: "#9A3B26",
    stationNames: [
      "Wu Kai Sha",
      "Ma On Shan",
      "Heng On",
      "Tai Shui Hang",
      "Shek Mun",
      "City One",
      "Sha Tin Wai",
      "Che Kung Temple",
      "Tai Wai",
      "Hin Keng",
      "Diamond Hill",
      "Kai Tak",
      "Sung Wong Toi",
      "To Kwa Wan",
      "Ho Man Tin",
      "Hung Hom",
      "East Tsim Sha Tsui",
      "Austin",
      "Nam Cheong",
      "Mei Foo",
      "Tsuen Wan West",
      "Kam Sheung Road",
      "Yuen Long",
      "Long Ping",
      "Tin Shui Wai",
      "Siu Hong",
      "Tuen Mun",
    ],
  },
  {
    id: "south-island",
    name: "South Island Line",
    color: "#B5BD00",
    stationNames: ["Admiralty", "Ocean Park", "Wong Chuk Hang", "Lei Tung", "South Horizons"],
  },
];

function stationId(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function lineIdsForStation(name: string): string[] {
  return MTR_LINES.filter((line) => line.stationNames.includes(name)).map((line) => line.id);
}

export const MTR_STATIONS: MtrStation[] = MTR_STATION_SEEDS.map((station) => ({
  ...station,
  id: stationId(station.name),
  lineIds: lineIdsForStation(station.name),
}));

export const MTR_STATION_BY_NAME = Object.fromEntries(
  MTR_STATIONS.map((station) => [station.name, station]),
);

export const MTR_LINE_BY_ID = Object.fromEntries(MTR_LINES.map((line) => [line.id, line]));

export const MTR_ACCESS_POINTS: MtrAccessPoint[] = MTR_ACCESS_POINT_ROWS.split(";")
  .map((row) => {
    const [stationName, label, latRaw, lngRaw] = row.split("|");
    const station = MTR_STATION_BY_NAME[stationName];
    if (!station) {
      return null;
    }
    return {
      id: `${station.id}-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${latRaw}-${lngRaw}`,
      stationName,
      label,
      lat: Number(latRaw),
      lng: Number(lngRaw),
      station,
    };
  })
  .filter((accessPoint): accessPoint is MtrAccessPoint => Boolean(accessPoint));

export function mtrLineNames(station: MtrStation): string[] {
  return station.lineIds
    .map((lineId) => MTR_LINE_BY_ID[lineId]?.name)
    .filter((name): name is string => Boolean(name));
}

export function mtrStationColor(station: MtrStation): string {
  const line = station.lineIds[0] ? MTR_LINE_BY_ID[station.lineIds[0]] : null;
  return line?.color ?? "#1f2937";
}

export function mtrAccessPointLabel(accessPoint: MtrAccessPoint): string {
  return accessPoint.label === "Access"
    ? `${accessPoint.stationName} access`
    : `${accessPoint.stationName} Exit ${accessPoint.label}`;
}

export function distanceMeters(
  from: { lat: number; lng: number },
  to: { lat: number; lng: number },
): number {
  const earthRadiusMeters = 6371000;
  const lat1 = (from.lat * Math.PI) / 180;
  const lat2 = (to.lat * Math.PI) / 180;
  const deltaLat = ((to.lat - from.lat) * Math.PI) / 180;
  const deltaLng = ((to.lng - from.lng) * Math.PI) / 180;
  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2;
  return Math.round(earthRadiusMeters * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)));
}

export function findNearestMtrStation(
  lat: number | null | undefined,
  lng: number | null | undefined,
): NearestMtrStation | null {
  if (lat === null || lat === undefined || lng === null || lng === undefined) {
    return null;
  }
  let nearest: NearestMtrStation | null = null;
  for (const accessPoint of MTR_ACCESS_POINTS) {
    const distance = distanceMeters({ lat, lng }, accessPoint);
    if (!nearest || distance < nearest.distanceMeters) {
      nearest = { station: accessPoint.station, accessPoint, distanceMeters: distance };
    }
  }
  if (nearest) {
    return nearest;
  }
  for (const station of MTR_STATIONS) {
    const distance = distanceMeters({ lat, lng }, station);
    if (!nearest || distance < nearest.distanceMeters) {
      nearest = { station, accessPoint: null, distanceMeters: distance };
    }
  }
  return nearest;
}

export function formatMtrDistance(distanceMetersValue: number): string {
  if (distanceMetersValue >= 1000) {
    return `${(distanceMetersValue / 1000).toFixed(1)} km`;
  }
  return `${Math.round(distanceMetersValue / 10) * 10} m`;
}
