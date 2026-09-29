import csv, json, collections, statistics as st
run="eval/runs/20260928-122309/per_query.csv"
Q={j["query_id"]:j for j in map(json.loads,open("eval/queries.jsonl"))}
R={}
for r in csv.DictReader(open(run)):
    R[(r["config"],r["strategy"],r["query_id"])]=int(r["rank"]) if r["rank"] else None
W=21
for s in ["fixed","semantic","sentence"]:
    hurt=[];help=[];tie=0
    for q in Q:
        f=R[("fusion",s,q)] or W; h=R[("hybrid",s,q)] or W
        if h>f: hurt.append((q,f,h))
        elif h<f: help.append((q,f,h))
        else: tie+=1
    def cross(lst,k):  # crossed top-k boundary
        return sum(1 for q,f,h in lst if (f<=k)!=(h<=k))
    print(f"\n== {s}: hurt {len(hurt)} help {len(help)} tie {tie}")
    print(" hurt: lost top5", cross(hurt,5), "lost top10",cross(hurt,10),"fell out of top20",sum(1 for _,f,h in hurt if h==W),
          "| drop size median", st.median(h-f for _,f,h in hurt), "drops<=2:",sum(1 for _,f,h in hurt if h-f<=2),
          "| hurt w/ fusion rank1:",sum(1 for _,f,h in hurt if f==1), "ends top5:",sum(1 for _,f,h in hurt if h<=5))
    print(" help: gained top5", cross(help,5), "gained top10",cross(help,10),"rescued from outside20",sum(1 for _,f,h in help if f==W),
          "| to rank1:",sum(1 for _,f,h in help if h==1))
    for name,lst in [("hurt",hurt),("help",help)]:
        ov=[Q[q]["word_overlap"] for q,_,_ in lst]; ln=[len(Q[q]["text"].split()) for q,_,_ in lst]
        hi=sum(1 for o in ov if o>=1.0)
        print(f" {name}: high-overlap {hi}/{len(lst)}  mean qlen {st.mean(ln):.1f}")
allov=sum(1 for q in Q if Q[q]["word_overlap"]>=1.0); print("\nall high",allov,"/",len(Q),"mean qlen",st.mean(len(Q[q]["text"].split()) for q in Q))
# consistency across strategies
hs=[{q for q in Q if (R[("hybrid",s,q)] or W)>(R[("fusion",s,q)] or W)} for s in ["fixed","semantic","sentence"]]
print("hurt in all 3:",len(hs[0]&hs[1]&hs[2]),"in any:",len(hs[0]|hs[1]|hs[2]))
