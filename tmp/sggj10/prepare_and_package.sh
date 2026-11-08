#!/usr/bin/env bash
set -euo pipefail
ROOT="ARCHIVES 8-30-2026/SGG/sggweb"
mkdir -p work out
unzip -q "$ROOT/SGGI1.3_COMPLETE_CLOUDFLARE_SITE.zip" -d work/base_deploy
unzip -q "$ROOT/SGGI1.3_SOURCE.zip" -d work/base_source
cp -a work/base_deploy work/build_site
cp -a work/base_source work/build_source
cp -a work/build_site/SGGI1.3 work/build_site/SGGJ1.0
cp -a work/build_source/SGGI1.3 work/build_source/SGGJ1.0
for root in work/build_site/SGGJ1.0 work/build_source/SGGJ1.0; do
  cd "$GITHUB_WORKSPACE/$root"
  mv SGGI1.3_BUILD_META.json SGGJ1.0_BUILD_META.json
  mv SGGI1.3_README.txt SGGJ1.0_README.txt
  mv SGGI1.3_TEST_RESULTS.txt SGGJ1.0_TEST_RESULTS.txt
  mv SGGI1.3_WORKER_DEPLOYMENT.txt SGGJ1.0_WORKER_DEPLOYMENT.txt
  mv sggi1_3.apk sggj1_0.apk
  mv sggi1_3.tar.gz sggj1_0.tar.gz
  printf 'J1.0\n' > VERSION
  for f in main.py play.html assets/main.py; do
    sed -i 's/SGGI1\.3/SGGJ1.0/g; s/I1\.3/J1.0/g; s/sggi1_3/sggj1_0/g' "$f"
  done
done
cd "$GITHUB_WORKSPACE"
printf '%s' 'H4sICOG872oCA2ZpbmlzaF90cmltLmpzALVb63LbRrL+76eYuFILag2Ckp1kz0phUrRESYx1K5K2yytpGRAYkohAAMEAlOhL1T7E+XNeb59ku3suuBC6ONnjKtsggJnp6en++uuegRdHImMzwbos5b/nQcpb1kxYW3vPPHqSuNmi/Ax/F0/fd63OMso6vpu5HTGf/za5jdMbSz8WQca72ML5LQ6i1nvbmuZB6E/wftGJiPPUa36PnhRvenma8ijrWqOjo192nG0zUMjnrrfuXuKDw5fOtmvZdLnj/PDDD8c8DA+DyA3LN4trc7Utr/qvnJfmakddQZ/WtR7thvPkIEhFN+K3bMSz1qUSzHYcR4piW27uB/HEC4PEuoYJPOt02GEaR1nbj+OULV2RLbjrs8CHdkG2dp7N4HZLDpDGccbiGbtERdms0IxUiG35PAnjtbV1vcU+PWOs1DRx55yaWkHk8ztnkS1x3iueigBekL9VM8Zkm1lJ9zi0jZ2AzPhGyGGBujPhpCDtYRDy0TryWjPbyrPZ/1jqJdHF50noerzVeZ3Gt4KnrO8HGQzJeqm3CFac/SgSN2Je6ArRfa4U1lZyPf/p8p8/Xr/48aqDL/3UmdvUb/mP9cf6VZbyo+xYCwzzuU1Bt6UJCXr05dkXWqrXaH8M+g2iDBcoBvMJ10ws4jSzGb9LwsALQDM85F4G2vfAAcJ4zmZpvGSwsgwECGYB99lgx3mlHzvKgOI0mKNBdn8ZnZ85iZsK3qqruOoOruATteilxfxNxJG1pdfCuMnSTcg0T92kpYdyTCN42lp1f7pc6Vv26rpoK833gAsvDRKct+iiqRSOtWvtL+JYcNZ3xdpmZ3G6dEOYERslwWy2ZvsL0BSP5tyhNzrqBZG5aQbaJOWMMncacrG30Ua+JvC94/7JyVywQRQ5bAxtZkEUiAUotOdl7DziDJAm9G32e84FtHAjn5YlDvBHygGxMjeIuO9Ytpa/hga71jEMG99yHrEw9m643/bgIfOKGYy01IU0NnOZgBnhlGIQg5rcBoCScD8OA59NXbBBn5Gfo1gzAE425esYroOsLg+KYTovxmZLMAQaodoA9Q/YEXKGwrNbN7xZcrGggeLZDGYQZTDcys1DNE93eU9H29DRBU4OVTlDfQDQpBxxN9PrY4PdpmmAiDIF27yZwcA00H78cRn/+1//J2A13eimvY7zonPCz13rFAQI2qcBvu5GK1eACsASYdHf8DCBoYKlC7+5IItQc3qHYle62sGu3PQGYGiom8Cqa7NGhaWulwEu4GRQOC8G9cMdn5SDE2HzNM6jkiUQnO9ah4DhGZocvjNV8JKCS4O3OdazL9ontOt0L9EV1K9djflwCwA85Ls6KrF//+t/2TgNlkuQYV++pVGLREDXNm93ADbXCqbhmV94Hqy0aky9ctmDA3pAy5Z6OwpceL7vLhOYP8yg47nUlsUgZugmLEvdSEjAROVkIJZs6Sr4zGL4GQgdW/X8WRLm8kUezBcQV1IO2lnBjCRCaHGE1CquTKGBjtSpmECrVcBvnSSa02tqkN0szfmzLxBQS5FrhWFLdi7Dk8LK0O8CZDlziLMrwuhgxlrfwO0tEA+mzBDq+jD5tGWdBkIE0RyRQJqAElbDMzrHepdZL2RPBhOTXCxanyB6Q7d2eQk24fBydf35M7zmlF6z9bxmbij4F+j7i2YscuAu9a1s1tbDGgNTb435XSZDgoB1iubBbN1Sj+woD0P75dYL6yoC1rMRv0oUASnDRogojbD1cHPFMB7uAEPkcb50ozbGLPIfpekwwAAU4HJI89E4bGKlDXjqhcCOYJ3Ac3NwYnQB6oRCjFMJRaSUS3Tck/5Rb/8D6x8MxoPzsxEb9se9wVn/gA3OmCaEtkV2ZniYMwvd7FRFPOsCxsHFt+9Z1hU0v956di1VgarectBj+pHferLqlSKQAKD+srsM1FfM5Wnqf7wTXAKND8oXIeR4gnXAyfNsMctD48tLWAOk6FqzuGhL3v11dDE4PPxgjdjR4HBMsKX0eBVdRQQ6AAwugQZimYYMBBJlH+3QnfJiIOQpEIeiKgWCTokFEal3sO/9t8Nh/2zMjnqn/YuT3ge8h0HeGMLcXWrTkWZEHcD6we92FrcJ99qEe0uMDml7E/B2qSF2CbDuxSGYJioJg4MbzWEQsL5g5WYqBJWQcrrW+JmgldJkoDEKFgEBXEisRdKDbENDLhBMHhI852mE7YgMlhA65Uuaj3BnHMikHwg3Rb3mQDDDirCgTeU+cnaktKM0X4IIEMwiS2AQSePQxrAXeDlYOXQEbjW1i6m2YeHmc45kJHTzyFvYbBZKNAeDs9kRKvkcJgqheeGuAvRNF/mtH6Cv58AIhLtCHiBJFjRHBgCKWnEcGSkHyJiWVCe5F9EGGBXQ/dZNcYIQpoHUyMXvDfePB+/6bDwcnOqFN0Q6Ar2CkcqFjyNQk46qTw1Iu0xzVZttsr7SPXOpL7bpAvmLvtiRs1SUwQGKBkwDliwAdbOjznFnYIZloEGkeRwtbBmjYCoZAB+ihFeoWaKBdySZ58aRQFehD5eS7NamVCG0NW2+6w9HAIdscAAONRgbVwqiNjmRzjRtw3CmkOJBgAFfwTzPZvclVtgKzFiqQNMDs1AUSlX6OitWqUNkRdrryfnr3gl7O+od9dnJ+RE7Ox/3jacjM4hhRY/CeAoh4K1AmnkCMfp9jBYPzunxJCM0kUZw1IY2s+AObtHEdISy2e0i8Bagn99kzNdwI7ggzXoAd5IAIcdeucjRsYeJ6kGqXAYlVG/iu6qbox3nu4mcxgQmMHl/PnzTH0JIZNSLi3qQckrLTNIYZYCVhsaXvfY/rovldYGHB+hLRfRTOsPxwUbUvNFaOKSEaGEmmwQ+BV5OZkSrsczBD6ecGSsiFgeucQfhF7sW83l7Tppth4VOAdeoN+wmvo14usdOIIqD6QpwvKzoDtIUXKizGOArO86nDIGLIUtC0NsP49yHwJpqAZZoGbfQScJT8HnENBgKu3a0dXUu1vOpOwd+gJyTSyk1ICILRMFIJtAeRA3Ivr0F925Ajl81TbqlWZzFGYauEtfeMDS5ThV7K2sQ8SWIcsT9mCUxJTVxtF6iOWqj4SuYk3iaXp3CqAFDtbLrJqJNuWK8oNgMvE0awxHQFoDcGBktdIB2rOHnF8D2gCSCJ7ywdUo8nzdZ9XNp1tqalVCSX5CR5UkSIkirnJw0Q4UnVzxs+60Z8JaoCNAa6TAWYiuVnG3twR3jHtoPFGAE8NNUA7SvkI+smzwEFfyag5lwRe3xIVXflBmoZTN9Jvk0hOWug4utDFbOWGtA64bI4BOXXPos0SPjriW/UF0W7kHKCKSbVbwkhzcIZzcc/R+DC6dmvmQ79BCUzcMZ9ohrhuQsA+ylFA9e12itIV8TRHi9o3M0W2G5FIOoOq5+hfibwpVCAzUtsOmyoOj5Bjq045f8Fulnt5w6m/qtTYwxBBuiewjbeI+Kv2i3u9bL7Zc/tHd22tt/I2KviOYkWyfwUBHTiSKmE5i+Nv+JLqzKvJMCpti9pOqfNSTzFRVVUcgg/WplgSFUoxp5W5xnsjtcMnwfOZshUDIbpiEK7qq549cm68gTFQGEibeBLG6OMzYJvfYwE6FlMWSZhDyrAHVpXsSpJJ8yvtyY39OMkNUIqogaDiSB4pWtEUNffE8Xx8SpFIQNcEDM2PP5wsRow3CKUNfAkQTPjBhvCdCEeld5XsXPNf4qfRQ4DBOXcESNIUEK74nTTRi0R41U32o7pBSqKXSVtOxYIO41VXskUXVlSacXhhuqJqtT/O8R/mxWTudGxmzRDG1tLXMeg9OlcGNONieTBWkRkCMAWGSud2PSgYL+FykBiR1lJLZKC2rJQJElEIlwBSwTw/JFQ56QR+C5FIhKuYJcU2QEE2QE3Jf1E8hgDJBOJM7QjtFE20PDaxKgJyDPRLKEjZfn4Lv5dIKEY4JERj8pynwow5CLPMxEwS9G4954sM8uevtvkF28650MDnpYf0BEvOiNRsRAZHqroAyBm7xkDkn+mtDRpMJTGcSWsQ+/Pde4+hQSKQpoOpOGPjDHE4IitO6LKBHYyAwLngksIdZDEZ2NJLokICOFjPY4QIpJJtyiVRIshyF05tDVlN108nojU4D3BUbCX3Ym2wzAEx0DtQYxEkYDVtPC3T98qLC4M80jHzCviPdb5REUGxz3hkW2J0Xr4Ao5yZqkVrdCsK+JvJ7wV68oNJV76128aSPSgT4RZ1H/ptdyd4/1g5FWK0q3wyhPc/AAYFwvjUU1bigdS/c1/EL/pLUlTdSXoD6u7u++bKy2YwgaFQYMsGSBBlRs+ZVrNHLTrzxeLcZrVfE718O1jNCIMb+DMXbNIFrAWh5+b9wojdeHAddFYKI9ZYCXOFxJDu4ypJSauzXErMpiA4LKodWIpmikIVSmFRrBym0HDbGrA2Grc2/Egic78PdlBz28jNHuFDsv4pYukjULPdYlrHurVTBtX7qqLAK1U6oj1QN/tRRgRqelq8IQTCPBPRF6R8OKZkUdpLJUu6ssVGMc3Uh1tUVotmmoMmoU+eVxh3IXGUsxikGWUxnnRK6c1CctvkpsHq4cQULHxv3RuH9QhqlKaqmczNal5caSocwvC93bZepeZrbFYkqjeIjhG67epMRHs3ok+2QlJit5MAf7owUAGX42sqbbAJxqyotMVWUE96RRZXKPuxu/nrw97VHmTd5+Nh5+YNuvvr+KhtLsdou68gGyelawesjrdAagSSHuQyL2rMoGjuSBKteQrwdgjGtZktB2raKOoEW4eDu8OB9R6r+PtR+ut2wRkam2Gq4LGPU3tr4oXhLbpaErhJek2GStSlFP4eBaVqpbhdqZdQLIaetM7nRvImpzua9dCSClXC+lPMffLM61WblEqPukBXXR1nXeSKdJaHezY7iAbfSkgxxE8Q6EYBXoGOVWKoszWw/Sf54a3NZVQY06dcEIe2z7KTSV9GkGOCEPaRQMOZBRaoabvB2jHKxaPl6Fxj6L7IMqI7RKJkRCz6AAGSh13Rml1YO31IBb6ibVo/V1tSJduVv6UVxuq0usTBeXO/rypdyvqdamMbAhfHRkMlbENQpqA4xqAwxr1SxMBpdK9bo5I9MmgJkZLlGAlfuo3VS3xoqHFyey1KRgqiFYsot6Qf9pGRFVmtU2ErsY9kf94TtD0Is9LEOWOyYEohBmu5/sjLwBAA08GXfEa2OSQlBfu81RpdhOKvaPZIGuXASoZv6SDuzpnVIM+JWEX+2BSMIvK0gEYJgKnsVF/WHJUR+BJ5M0JiBRWKLPlXKyIl2jBE7ldDIDVHkinqtoTNVUAYXIMB6I8rXiZeUVkX///PQC9P56cAKoxA4HZweDsyPtWGRlMuryuyROEWu9OMVy+/NRvUw/cwEW/d3GWv1ziFKei9kLasyY42akK1iLVKAObNWNBEOEq1sA1WJpXqo43FdMeHodQQ5V0ILm+iF6QqBTN11scO8vNzxSyK+mrQAbRWJYKgyVE1jFx0zi6s7R4rMS2UQkbk/BRLwF7hKwKawBGx33RFOSS1BO3nixzhYYIaUEBAzy9Nbm9lS5VkzSiDUMlsZR8JHsr11OI7GLWh6o4pGqmMujTXALV1YlqxSqTJjRa6dPi5jE3K2FKU1WMRuXAMHoKJgKMjoIyC0yw5Kb0yWZZpEMj2c2lWFVfrNXJSi1XclKi3rOUiGvbfYa52rYiqZUugpRrWooR6D6xUY1QjL1EwqvRNdV+ZgY+rTK2gm+MgKkTRJe5t8bhJvQSoKKNFNVT6lsRKldEDQsIrnqAU0/4neZzgVAAF3kpm2urLr11by5RTT4/oO70savy6eZ/PpRW80T8DjSA+dCfFvXzCfDfu/gtK+OhMiTHF/RWqYQkwOIl+cfToFDqo6KvbWv6Oz128HJweS0P+7pY0K100vI/ipHl76ic7QcmOzo7cl4pIQsVei+oiNMTih96qM/Ql6ij9PEczqphSdpZHEbd/3AY0tMRkOCH6TEDNd154EgyXnl8DbtjIENqAO90JJEQ4vYKptC0q2dHMKG5oAbtEYfkLPacgJxoCVobbG//IV1/qlDTsdBtbSoNT75Rh9PdyAayNv6uDeKtJRd2p+guxwmt+J0Gs+GGXjy8os5CV0oJp6KmFAhixPQzYrO/GAgl5u3fiCALfmliLpXKZIRHKpsfwH/VUtodDL6qzSIGiINHO1cOa2fd199/u7z91t1TeDFN136WuDeTNraKmulYUEeVZSRZQCylEX4kz2T+jUpLufAtMcqFkgCDY9AzF7qcr08DB2JPKV9QkRcl5hPW1VkChYDBESXySqb7HXbfESHe8/wOwHZlA7s1U+zy0fFVwOlV4vL4huCq84Vre7VlX/14qp19fPu1dWVI39tXf189e1VJ+jMbavwAnj2ooWv4Vsvtv4K15du++M1/rPd/vv1X7d+/rYT4NB0fLQ0qGJ9ovUHeius8b/X48ahVrXGmtgEIcbflM/5HVMKI/YmabNFlrMBjEr/hZDyGCLQr3X9ndrK62POBk6bLUCdSJTfTejsUIYqSWIxMmpiJVmfU/pKaHjviUTMz0/7B5RfnPTHfbZ/cv724PCkN+yz0UAe8Kidg9ytcu3iIw1d6N4oYD58ooxSiD94+KuUpNROesnaUGl/vVS4KOWrldOWOnfdPHCpamcgZVY5N/mn9p7vKUHrbXCTfartdYeNuCkudjb5ir3xrDE0m/p75dU6HXiw3FocczE5nZs9XFGl7aZagbuceSJo5lxsHNZ6PH/bqNXqBoDEGyeyIK3ngTxUWasQR8XRovsPXDx6OlmuxgRm+L7/WhGhwgGfdjj50T4QCbBtrc5DDoh+aupAap3AfPx4NtOAIN8e1T8LrH/8JqEc5KWityBhy00rAbj84JHAi7iYGMZhP9Tyi5osnsJQk2mDeRBR1JQR81skNw1ZWrWYjCizpwuN5qsds4mr07EqaFFKpfCqsvconkSptKI2SNXldvv7628rjOrzZ+qmKxkVVhQtvGe4DzR5VW3SwDvrq/k0joVk9M/MBqLt9uedzy8///eJ4tdMw8h0DDJt15X7NSTy6aM2Ku5STfVV81Q13Xt53+ON2xPZYFs+LgACxyCEqN38rummTMyu702SSpPeA13WXD+p6upRtcgB+DLJ1rgF1QA09NWl+QZ5c0TTtjKyufuIBIgbbyBVY/gdn9yOq9TEysUuVWOh/QyZRWEhmPa2fGeDyG3MxHA4dagB8HpztuZZAzW8v8fi67WmPktPv6rX6lGQxq7rrzzcf+NHUY9+9fSEPhs/1Hna9zzKBoZc7pTx5ZT7vj7dLvkf12d96AvNWkFah8tP/I57WsAvXfOpPsSL0J8kaexxQTlaU6Gqme03TEE/Ue5ZHrNlZW5q2ZdW2/s4A6dW1VUH7jrzj5ZeK+va/uTd+rs49pdyoaPsxNXqmOnKTW5AYeRmeRQG0c0T3t7bEPNjkJCYf//dqr5cWD8sVcMhobroqjTSRh/Vcd+sn97mpYXDPA1oHe2nyHq0jOD4qRZ57v87P/kPYiPZleJBAAA=' | base64 -d | gzip -dc > tmp/sggj10/finish_trim.js
sed -i "s|const W='/mnt/data/sggj_work';|const W=process.cwd()+'/work';|" tmp/sggj10/finish_trim.js
node --check tmp/sggj10/finish_trim.js
node tmp/sggj10/finish_trim.js
cp work/build_site/SGGG1.4_GLOBAL_LOG_WORKER.js work/build_source/SGGG1.4_GLOBAL_LOG_WORKER.js
cp work/build_site/SGGG1.4_GLOBAL_LOG_WORKER.js work/build_source/SGGJ1.0/SGGJ1.0_GLOBAL_LOG_WORKER.js
rm -rf work/build_source/deploy
cp -a work/build_site work/build_source/deploy
find work/build_site work/build_source -type d -name __pycache__ -prune -exec rm -rf {} +
find work/build_site work/build_source -type f -name '*.pyc' -delete
mkdir -p out
( cd work/build_site && zip -qr -9 "$GITHUB_WORKSPACE/out/SGGJ1.0_COMPLETE_CLOUDFLARE_SITE.zip" . )
( cd work/build_source && zip -qr -9 "$GITHUB_WORKSPACE/out/SGGJ1.0_SOURCE.zip" . )
unzip -tq out/SGGJ1.0_COMPLETE_CLOUDFLARE_SITE.zip
unzip -tq out/SGGJ1.0_SOURCE.zip
sha256sum out/*.zip > out/SHA256SUMS.txt
node - <<'NODE'
const fs=require('fs'), path=require('path');
const site='work/build_site';
const catalog=JSON.parse(fs.readFileSync(path.join(site,'versions.json'),'utf8'));
if(catalog.versions.length!==9 || catalog.versions[0].version!=='SGGJ1.0' || catalog.versions.filter(v=>v.current).length!==1) throw new Error('selector validation failed');
for(const v of catalog.versions) if(!fs.existsSync(path.join(site,v.path))) throw new Error('missing selector path '+v.path);
for(const d of ['SGGF2.0a','SGGF1.666HellFinal','SGGF1.666','SGGF1.6','SGGF1.0','SGGE3.2','SGGE3.1','SGGE2.0','SGGJ1.0']) if(!fs.existsSync(path.join(site,d))) throw new Error('missing kept version '+d);
for(const d of ['SGGG1.3','SGGG1.4','SGGG1.5','SGGH1.0','SGGI1.0','SGGI1.1','SGGI1.2','SGGI1.3']) if(fs.existsSync(path.join(site,d))) throw new Error('test version remains '+d);
const main=fs.readFileSync(path.join(site,'SGGJ1.0','main.py'),'utf8');
if(!main.includes('VERSION = "J1.0"') || !main.includes("postGlobalSession('SGGJ1.0'")) throw new Error('current runtime identity failure');
const page=fs.readFileSync(path.join(site,'index.html'),'utf8');
if(!page.includes('Browser Edition Archive <span class="current-version">SGGJ1.0</span>')) throw new Error('masthead mismatch');
const worker=fs.readFileSync(path.join(site,'SGGG1.4_GLOBAL_LOG_WORKER.js'),'utf8');
if(!worker.includes('/^SGG[A-Z]')) throw new Error('Worker validator mismatch');
console.log('Selector, kept versions, test-version pruning, runtime labels, masthead and Worker validator all verified.');
NODE
echo "PACKAGE SIZES:"
du -h out/*.zip
