# -*- coding: utf-8 -*-

import threading
import time
import cookielib
import urllib2
import urllib#编码请求字串，用于处理验证码
import socket#用于捕获超时错误
import zlib
import pickle
import os

from contentParse import ParseQuestion
from httpLib import *
from helper import *


class PageWorker(object):
    def __init__(self, conn = None, maxThread = 1, targetUrl = ''):
        self.conn         = conn
        self.cursor       = conn.cursor()
        self.maxPage      = ''
        self.maxThread    = maxThread
        self.url          = targetUrl
        self.suffix       = ''
        self.setCookie()
        self.workSchedule = {}
        self.setWorkSchedule()
        self.addProperty()
        
    def getMaxPage(self, content):
        try:
            pos      = content.index(u'">下一页</a></span>')
            rightPos = content.rfind(u"</a>",0,pos)
            leftPos  = content.rfind(u">",0,rightPos)
            maxPage  = int(content[leftPos+1:rightPos])
            print u"答案列表共计{}页".format(maxPage)
            return maxPage
        except:
            print u"答案列表共计1页"
            return 1
    
    def setWorkSchedule(self):
        self.workSchedule = {}
        content      = self.getHttpContent('http://www.zhihu.com/question/27622564', extraHeader = self.extraHeader)
        print 'hellp'
        print content
        exit()
        content      = self.getHttpContent(self.url + self.suffix + str(self.maxPage))
        self.maxPage = self.getMaxPage(content)
        for i in range(self.maxPage):
            self.workSchedule[i] = self.url + self.suffix + str(i)
    
    def addProperty(self):
        return
    
    #set cookieJar
    def loadCookJar(self, content = ''):
        fileName = u'./theFileNameIsSoLongThatYouWontKnowWhatIsThat.txt' 
        f = open(fileName, 'w')
        f.write(content)
        f.close()
        self.cookieJarInMemory.load(fileName)
        os.remove(fileName)
        return 

    def setCookie(self):
        self.cookieJarInMemory = cookielib.LWPCookieJar()
        rowcount = self.cursor.execute('select count(Pickle) from VarPickle where Var = "PostHeader"').fetchone()[0]    
        pickleVar  = self.cursor.execute("select Pickle from VarPickle where Var='PostHeader'").fetchone()[0] 
        cookieVar  = pickle.loads(pickleVar)
        recordDate = cookieVar[0]
        cookieJar  = cookieVar[1]
        self.loadCookJar(cookieJar)
        
        cookieStr = ''
        for cookie in self.cookieJarInMemory:
            cookieStr += cookie.name + '=' + cookie.value + ';'
        self.extraHeader = {
                'User-Agent':    'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:34.0) Gecko/20100101 Firefox/34.0',
                'Referer':    'www.zhihu.com/',
                'Host':   'www.zhihu.com',
                'DNT':    '1',
                'Connection': 'keep-alive',
                'Cache-Control':  'max-age=0',
                'Accept-Language':    'zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3',
                #'Accept-Encoding':    'gzip, deflate',mao si bu neng yong
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Cookie': cookieStr
        }

        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookieJarInMemory))
        urllib2.install_opener(self.opener)
        return 


    def getHttpContent(self, url='', extraHeader={} , data=None, timeout=5):
        u"""获取网页内容
     
        获取网页内容, 打开网页超过设定的超时时间则报错
        
        参数:
            url         一个字符串,待打开的网址
            extraHeader 一个简单字典,需要添加的http头信息
            data        需传输的数据,默认为空
            timeout     int格式的秒数，打开网页超过这个时间将直接退出，停止等待
        返回:
            pageContent 打开成功时返回页面内容，字符串或二进制数据|失败则返回空字符串
        报错:
            IOError     当解压缩页面失败时报错
        """
        if data == None:
            request = urllib2.Request(url = url)
        else:
            request = urllib2.Request(url = url, data = data)
        for headerKey in extraHeader.keys():
            request.add_header(headerKey, extraHeader[headerKey])
        try: 
            rawPageData = urllib2.urlopen(request, timeout = timeout)
        except  urllib2.HTTPError as error:
            print u'网页打开失败'
            print u'错误页面:' + url
            if hasattr(error, 'code'):
                print u'失败代码:' + str(error.code)
            if hasattr(error, 'reason'):
                print u'错误原因:' + error.reason
        except  urllib2.URLError as error:
            print u'网络连接异常'
            print u'错误页面:' + url
            print u'错误原因:'
            print error.reason
        except  socket.timeout as error:
            print u'打开网页超时'
            print u'超时页面' + url
        else:
            return self.decodeGZip(rawPageData)
        return ''

    def decodeGZip(self, rawPageData):
        u"""返回处理后的正常网页内容
     
        判断网页内容是否被压缩，无则直接返回，若被压缩则使用zlip解压后返回
        
        参数:
            rawPageData   urlopen()传回的fileLike object
        返回:
            pageContent   页面内容，字符串或二进制数据|解压缩失败时则返回空字符串
        报错:
            无
        """
        if rawPageData.info().get(u"Content-Encoding") == "gzip":
            try:
                pageContent = zlib.decompress(rawPageData.read(), 16 + zlib.MAX_WBITS)
            except zlib.error as ziperror:
                print u'解压出错'
                print u'出错解压页面:' + rawPageData.geturl()
                print u'错误信息：'
                print zliberror
                return ''
        else:
            pageContent = rawPageData.read()
            return pageContent

class QuestionWorker(PageWorker):
    def boss(self):
        maxTry = self.maxTry
        while maxTry > 0 and len(self.workSchedule) > 0:
            self.leader()
            maxTry -= 1
        return 
    
    def leader(self):
        threadPool = []
        for key in self.workSchedule:
            threadPool.append(threading.Thread(target=self.worker, kwargs={'workNo':key}))

        threadsCount = len(threadPool)
        while threadsCount > 0:
            bufCount = self.maxThread - threading.activeCount()
            if bufCount > 0:
                while bufCount > 0 and threadsCount > 0:
                    threadPool[threadsCount - 1].start()
                    bufCount    -= 1
                    threadsCount -= 1
                    time.sleep(0.1)
            else:
                print u'正在读取答案页面，还有{}张页面等待读取'.format(threadsCount)
                time.sleep(1)
        self.conn.commit()
    
    def worker(self, workNo = 0):
        u"""
        worker只执行一次，待全部worker执行完毕后由调用函数决定哪些worker需要再次运行
        重复的次数由self.maxTry指定
        这样可以给知乎服务器留出生成页面缓存的时间
        """
        content = self.getHttpContent(url = self.workSchedule[workNo], extraHeader = self.extraHeader, timeout = self.waitFor)
        if content == '':
            return
        parse = ParseQuestion(content)
        questionInfoDict, answerDictList = parse.getInfoDict()
        save2DB(self.cursor, questionInfoDict, 'questionID', 'QuestionInfo')
        for answerDict in answerDictList:
            save2DB(self.cursor, answerDict, 'answerHref', 'AnswerContent')
        del self.workSchedule[i]
        return 

    def addProperty(self):
        self.maxPage   = 1
        self.suffix    = '?sort=created&page='
        self.maxTry    = 5
        self.waitFor   = 5
        return
"""
class JsonWorker:
"""
